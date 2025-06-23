from livekit.agents import llm
from livekit import rtc
from livekit.plugins import openai, elevenlabs
from config import FIELDS, FIELD_ORDER, NUM_FIELDS, WAKE_WORDS
from utils import clean_user_text, is_repeat_request, is_off_topic, infer_plate_from_text, infer_eta_from_text
from prompts import WELCOME_MESSAGE, ASK_MESSAGE, CONFIRM_MESSAGE, REPEAT_MESSAGE, OFF_TOPIC_MESSAGE, PERMISSION_MESSAGE
from daisy_assistant_fnc import DaisyAssistantFnc
import asyncio
import logging
import openai as openai_client_asyn

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class ConversationStateMachine:
    def __init__(self, stt: openai.STT, openai_client: openai_client_asyn.AsyncOpenAI, assistant_fnc: DaisyAssistantFnc, tts: elevenlabs.TTS, audio_source: rtc.AudioSource):
        self.stt = stt
        self.openai_client = openai_client
        self.assistant_fnc = assistant_fnc
        self.tts = tts
        self.audio_source = audio_source
        self.audio_buffer = []
        self.state = {
            "state": "waiting_wake",
            "idx": 0,
            "fields": {k: None for k, _ in FIELDS},
            "route": "Ruta desconocida",
            "confirmation_attempts": 0
        }
        logger.debug("Inicializando máquina de estados")

    async def _get_llm_response(self, prompt: str) -> str:
        """Obtiene una respuesta de texto del LLM."""
        logger.debug(f"Enviando prompt al LLM: {prompt}")
        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": prompt}
                ]
            )
            text = response.choices[0].message.content
            logger.debug(f"Respuesta del LLM: {text}")
            return text.strip() if text.strip() else prompt
        except Exception as e:
            logger.error(f"Error al obtener respuesta del LLM: {str(e)}")
            return prompt

    async def _send_audio_message(self, content: str):
        """Convierte texto a audio con ElevenLabs."""
        logger.debug(f"Enviando audio: {content}")
        stream = self.tts.stream()
        playout_q = asyncio.Queue()
        
        async def _synth_task():
            stream.push_text(content)
            stream.flush()
            stream.end_input()
            frame_count = 0
            async for ev in stream:
                await playout_q.put(ev.frame)
                frame_count += 1
            logger.debug(f"Frames generados: {frame_count}")
            await playout_q.put(None)

        async def _playout_task():
            while True:
                frame = await playout_q.get()
                if frame is None:
                    break
                await self.audio_source.capture_frame(frame)

        synth_task = asyncio.create_task(_synth_task())
        playout_task = asyncio.create_task(_playout_task())
        await asyncio.gather(synth_task, playout_task)
        await stream.aclose()
        logger.debug(f"Audio enviado: {content}")

    async def send_welcome(self):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        response = await self._get_llm_response(WELCOME_MESSAGE)
        await self._send_audio_message(response)

    async def process_user_input(self, msg: llm.ChatMessage):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        try:
            if isinstance(msg.content, list):
                msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
        except Exception as e:
            logger.error(f"Error al procesar contenido: {str(e)}")
            return
        user_text = msg.content
        user_text_lower = user_text.lower()
        if is_repeat_request(user_text_lower):
            await self.handle_repeat()
        elif is_off_topic(user_text_lower):
            await self.handle_off_topic()
        elif self.state["state"] == "waiting_wake":
            await self.handle_waiting_wake(user_text_lower)
        elif self.state["state"] == "waiting_permission":
            await self.handle_waiting_permission(msg.content)
        elif self.state["state"] == "asking":
            await self.handle_asking(msg.content)
        elif self.state["state"] == "confirm":
            await self.handle_confirm(user_text_lower)

    async def handle_repeat(self):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        repeat_message = REPEAT_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        response = await self._get_llm_response(repeat_message)
        await self._send_audio_message(response)

    async def handle_off_topic(self):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        off_topic_message = OFF_TOPIC_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        response = await self._get_llm_response(off_topic_message)
        await self._send_audio_message(response)

    async def handle_waiting_wake(self, user_text_lower: str):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        if any(user_text_lower.startswith(w) for w in WAKE_WORDS):
            logger.debug("FSM: Transición a waiting_permission")
            self.state["state"] = "waiting_permission"
            permission_request = "¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"
            response = await self._get_llm_response(permission_request)
            await self._send_audio_message(response)

    async def handle_waiting_permission(self, user_text: str):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        permission_prompt = PERMISSION_MESSAGE.format(text=user_text)
        response = await self._get_llm_response(permission_prompt)
        intent = "aceptar_llamada"  # Placeholder
        if intent == "aceptar_llamada":
            logger.debug("FSM: Transición a asking")
            self.state["state"] = "asking"
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            response = await self._get_llm_response(ask_message)
            await self._send_audio_message(response)
        elif intent == "rechazar_llamada":
            logger.debug("FSM: Transición a ended")
            end_message = "Entendido. Te contacto luego. ¡Échale un ojo a la ruta!"
            response = await self._get_llm_response(end_message)
            await self._send_audio_message(response)
            self.state["state"] = "ended"
            await self.assistant_fnc.save_driver_data()

    async def handle_asking(self, user_text: str):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        current_field = FIELD_ORDER[self.state["idx"]]
        cleaned = clean_user_text(user_text, current_field)
        if cleaned.lower() not in {"sí", "si", "no", "correcto", "incorrecto"}:
            logger.debug(f"FSM: Procesando dato para {current_field}: {cleaned}")
            try:
                if current_field == "nombre_operador":
                    await self.assistant_fnc.set_driver_name(cleaned)
                elif current_field == "numero_tractor":
                    await self.assistant_fnc.set_tractor_number(cleaned)
                elif current_field == "placas_tractor":
                    plate = await infer_plate_from_text(cleaned)
                    if not plate:
                        logger.debug(f"FSM: Placa inválida, repitiendo para {current_field}")
                        ask_message = ASK_MESSAGE.format(
                            field_name=FIELDS[self.state["idx"]][1],
                            remaining=NUM_FIELDS - self.state["idx"]
                        )
                        response = await self._get_llm_response(ask_message)
                        await self._send_audio_message(response)
                        return
                    await self.assistant_fnc.set_tractor_plates(cleaned)
                    cleaned = plate
                elif current_field == "numero_trailer":
                    await self.assistant_fnc.set_trailer_number(cleaned)
                elif current_field == "placas_trailer":
                    plate = await infer_plate_from_text(cleaned)
                    if not plate:
                        logger.debug(f"FSM: Placa inválida, repitiendo para {current_field}")
                        ask_message = ASK_MESSAGE.format(
                            field_name=FIELDS[self.state["idx"]][1],
                            remaining=NUM_FIELDS - self.state["idx"]
                        )
                        response = await self._get_llm_response(ask_message)
                        await self._send_audio_message(response)
                        return
                    await self.assistant_fnc.set_trailer_plates(cleaned)
                    cleaned = plate
                elif current_field == "eta":
                    eta = await infer_eta_from_text(cleaned)
                    if not eta:
                        logger.debug(f"FSM: ETA inválido, repitiendo para {current_field}")
                        ask_message = ASK_MESSAGE.format(
                            field_name=FIELDS[self.state["idx"]][1],
                            remaining=NUM_FIELDS - self.state["idx"]
                        )
                        response = await self._get_llm_response(ask_message)
                        await self._send_audio_message(response)
                        return
                    await self.assistant_fnc.set_eta(eta)
                    cleaned = eta
            except Exception as e:
                logger.error(f"Error en DaisyAssistantFnc para {current_field}: {str(e)}")
                ask_message = ASK_MESSAGE.format(
                    field_name=FIELDS[self.state["idx"]][1],
                    remaining=NUM_FIELDS - self.state["idx"]
                )
                response = await self._get_llm_response(ask_message)
                await self._send_audio_message(response)
                return
            confirm_message = CONFIRM_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                value=" ".join(cleaned) if current_field in ("placas_tractor", "placas_trailer") else cleaned
            )
            self.state["fields"][current_field] = cleaned
            self.state["state"] = "confirm"
            self.state["confirmation_attempts"] = 0
            response = await self._get_llm_response(confirm_message)
            await self._send_audio_message(response)
        else:
            logger.debug(f"FSM: Respuesta inválida, repitiendo para {current_field}")
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            response = await self._get_llm_response(ask_message)
            await self._send_audio_message(response)

    async def handle_confirm(self, user_text_lower: str):
        logger.debug(f"FSM: Estado -> {self.state['state']}")
        current_field = FIELD_ORDER[self.state["idx"]]
        self.state["confirmation_attempts"] += 1
        if user_text_lower in {"sí", "si", "correcto", "sí está bien", "está bien"}:
            self.state["idx"] += 1
            self.state["confirmation_attempts"] = 0
            if self.state["idx"] >= NUM_FIELDS:
                logger.debug("FSM: Todos los campos recolectados, transición a ended")
                end_message = "¡Gracias por los datos! Todo listo, ¡buen viaje!"
                response = await self._get_llm_response(end_message)
                await self._send_audio_message(response)
                self.state["state"] = "ended"
                try:
                    await self.assistant_fnc.save_driver_data()
                except Exception as e:
                    logger.error(f"Error al guardar JSON: {str(e)}")
                return
            logger.debug(f"FSM: Transición a asking para {FIELD_ORDER[self.state['idx']]}")
            self.state["state"] = "asking"
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            response = await self._get_llm_response(ask_message)
            await self._send_audio_message(response)
        elif user_text_lower in {"no", "incorrecto", "no está bien"} or self.state["confirmation_attempts"] >= 3:
            logger.debug(f"FSM: Dato rechazado o demasiados intentos, repitiendo para {current_field}")
            self.state["fields"][current_field] = None
            self.state["state"] = "asking"
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            response = await self._get_llm_response(ask_message)
            await self._send_audio_message(response)
        else:
            logger.debug(f"FSM: Respuesta ambigua, pidiendo confirmación para {current_field}")
            confirm_message = CONFIRM_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                value=" ".join(self.state["fields"][current_field]) if current_field in ("placas_tractor", "placas_trailer") else self.state["fields"][current_field]
            )
            response = await self._get_llm_response(confirm_message)
            await self._send_audio_message(response)
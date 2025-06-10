from livekit.agents import llm
from config import FIELDS, FIELD_ORDER, NUM_FIELDS, WAKE_WORDS
from utils import clean_user_text, is_repeat_request, is_off_topic, infer_plate_from_text
from daisy_prompts import WELCOME_MESSAGE, ASK_MESSAGE, CONFIRM_MESSAGE, REPEAT_MESSAGE, OFF_TOPIC_MESSAGE, PERMISSION_MESSAGE
from daisy_assistant_fnc import DaisyAssistantFnc
import time
import logging
from unidecode import unidecode

# Configura el logger para state_machine
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Clase que maneja la máquina de estados de la conversación
class ConversationStateMachine:
    def __init__(self, session, assistant_fnc: DaisyAssistantFnc):
        # Almacena la sesión de LiveKit
        self.session = session
        self.assistant_fnc = assistant_fnc
        # Estado inicial de la conversación
        self.state = {
            "state": "waiting_wake",
            "idx": 0,
            "fields": {k: None for k, _ in FIELDS},
            "route": "Ruta desconocida",
            "confirmation_attempts": 0  # Contador de intentos de confirmación
        }
        logger.debug(f"Inicializando máquina de estados para sesión ")

    async def send_welcome(self):
        """
        Envía el mensaje de bienvenida y lo registra
        """
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="assistant",
                content=WELCOME_MESSAGE
            )
        )
        self.session.response.create()

    async def process_user_input(self, msg: llm.ChatMessage):
        """
        Procesa la entrada del usuario
        """
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        start_time = time.time()
        # Convierte el contenido del mensaje si es una lista
        try:
            if isinstance(msg.content, list):
                msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
        except Exception as e:
            logger.error(f"Error al procesar contenido del mensaje: {str(e)}")
            return
        user_text = msg.content
        user_text_lower = user_text.lower()
        # Maneja solicitudes de repetición
        if is_repeat_request(user_text_lower):
            await self.handle_repeat()
        # Maneja respuestas fuera de tema
        elif is_off_topic(user_text_lower):
            await self.handle_off_topic()
        # Maneja los diferentes estados de la conversación
        elif self.state["state"] == "waiting_wake":
            await self.handle_waiting_wake(user_text_lower)
        elif self.state["state"] == "waiting_permission":
            await self.handle_waiting_permission(msg.content)
        elif self.state["state"] == "asking":
            await self.handle_asking(msg.content)
        elif self.state["state"] == "confirm":
            await self.handle_confirm(user_text_lower)
        end_time = time.time()
        latency_ms = (end_time - start_time) * 1000
        logger.debug(f"Latencia del LLM ({self.state['state']}): {latency_ms:.2f} ms")

    async def handle_repeat(self):
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        repeat_message = REPEAT_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=repeat_message
            )
        )
        self.session.response.create()

    async def handle_off_topic(self):
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        off_topic_message = OFF_TOPIC_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=off_topic_message
            )
        )
        self.session.response.create()

    async def handle_waiting_wake(self, user_text_lower: str):
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        if any(user_text_lower.startswith(w) for w in WAKE_WORDS):
            logger.debug(f"FSM: Transición a waiting_permission")
            self.state["state"] = "waiting_permission"
            permission_request = "¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=permission_request
                )
            )
            self.session.response.create()

    async def handle_waiting_permission(self, user_text: str):
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        permission_prompt = PERMISSION_MESSAGE.format(text=user_text)
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=permission_prompt
            )
        )
        intent = "aceptar_llamada"  # Placeholder, debe venir del modelo
        if intent == "aceptar_llamada":
            logger.debug(f"FSM: Transición a asking")
            self.state["state"] = "asking"
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=ask_message
                )
            )
            self.session.response.create()
        elif intent == "rechazar_llamada":
            logger.debug(f"FSM: Transición a ended")
            end_message = "Entendido. Te contacto luego. ¡Échale un ojo a la ruta!"
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=end_message
                )
            )
            self.state["state"] = "ended"
            await self.assistant_fnc.save_driver_data()  # Guardar JSON incluso si se rechaza

    async def handle_asking(self, user_text: str):
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        current_field = FIELD_ORDER[self.state["idx"]]
        cleaned = clean_user_text(user_text, current_field)
        if cleaned.lower() not in {"sí", "si", "no", "correcto", "incorrecto"}:
            logger.debug(f"FSM: Procesando dato para {current_field}: {cleaned}")
            # Invoca la función correspondiente de DaisyAssistantFnc
            try:
                if current_field == "nombre_operador":
                    await self.assistant_fnc.set_driver_name(cleaned)
                elif current_field == "numero_tractor":
                    await self.assistant_fnc.set_tractor_number(cleaned)
                elif current_field == "placas_tractor":
                    plate = await infer_plate_from_text(cleaned, self.session)
                    if not plate:
                        logger.debug(f"FSM: Placa inválida, repitiendo pregunta para {current_field}")
                        ask_message = ASK_MESSAGE.format(
                            field_name=FIELDS[self.state["idx"]][1],
                            remaining=NUM_FIELDS - self.state["idx"]
                        )
                        self.session.conversation.item.create(
                            llm.ChatMessage(
                                role="assistant",
                                content=ask_message
                            )
                        )
                        self.session.response.create()
                        return
                    await self.assistant_fnc.set_tractor_plates(cleaned)
                    cleaned = plate
                elif current_field == "numero_trailer":
                    await self.assistant_fnc.set_trailer_number(cleaned)
                elif current_field == "placas_trailer":
                    plate = await infer_plate_from_text(cleaned, self.session)
                    if not plate:
                        logger.debug(f"FSM: Placa inválida, repitiendo pregunta para {current_field}")
                        ask_message = ASK_MESSAGE.format(
                            field_name=FIELDS[self.state["idx"]][1],
                            remaining=NUM_FIELDS - self.state["idx"]
                        )
                        self.session.conversation.item.create(
                            llm.ChatMessage(
                                role="assistant",
                                content=ask_message
                            )
                        )
                        self.session.response.create()
                        return
                    await self.assistant_fnc.set_trailer_plates(cleaned)
                    cleaned = plate
            except Exception as e:
                logger.error(f"Error al invocar función de DaisyAssistantFnc para {current_field}: {str(e)}")
                # Repite la pregunta si falla
                ask_message = ASK_MESSAGE.format(
                    field_name=FIELDS[self.state["idx"]][1],
                    remaining=NUM_FIELDS - self.state["idx"]
                )
                self.session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content=ask_message
                    )
                )
                self.session.response.create()
                return
            # Confirmación con formato más claro para placas
            confirm_message = CONFIRM_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                value=" ".join(cleaned) if current_field in ("placas_tractor", "placas_trailer") else cleaned
            )
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=confirm_message
                )
            )
            self.state["fields"][current_field] = cleaned
            self.state["state"] = "confirm"
            self.state["confirmation_attempts"] = 0
            self.session.response.create()
        else:
            logger.debug(f"FSM: Respuesta inválida, repitiendo pregunta para {current_field}")
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=ask_message
                )
            )
            self.session.response.create()

    async def handle_confirm(self, user_text_lower: str):
        logger.debug(f"FSM: Estado actual -> {self.state['state']}")
        current_field = FIELD_ORDER[self.state["idx"]]
        self.state["confirmation_attempts"] += 1
        if user_text_lower in {"sí", "si", "correcto", "sí está bien", "está bien"}:
            self.state["idx"] += 1
            self.state["confirmation_attempts"] = 0
            if self.state["idx"] >= NUM_FIELDS:
                logger.debug(f"FSM: Todos los campos recolectados, transición a ended")
                end_message = "¡Gracias por los datos! Todo listo, ¡buen viaje!"
                self.session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content=end_message
                    )
                )
                self.state["state"] = "ended"
                try:
                    await self.assistant_fnc.save_driver_data()  # Guardar JSON con DaisyAssistantFnc
                except Exception as e:
                    logger.error(f"Error al guardar JSON: {str(e)}")
                return
            logger.debug(f"FSM: Transición a asking para campo {FIELD_ORDER[self.state['idx']]}")
            self.state["state"] = "asking"
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=ask_message
                )
            )
            self.session.response.create()
        elif user_text_lower in {"no", "incorrecto", "no está bien"} or self.state["confirmation_attempts"] >= 3:
            logger.debug(f"FSM: Dato rechazado o demasiados intentos, repitiendo pregunta para {current_field}")
            self.state["fields"][current_field] = None
            self.state["state"] = "asking"
            ask_message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=ask_message
                )
            )
            self.session.response.create()
        else:
            logger.debug(f"FSM: Respuesta ambigua, pidiendo confirmación de nuevo para {current_field}")
            confirm_message = CONFIRM_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                value=" ".join(self.state["fields"][current_field]) if current_field in ("placas_tractor", "placas_trailer") else self.state["fields"][current_field]
            )
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=confirm_message
                )
            )
            self.session.response.create()
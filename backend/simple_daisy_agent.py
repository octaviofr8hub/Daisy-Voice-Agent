'''
Versión corregida del agente de voz usando STT, LLM y TTS de OpenAI
'''
from __future__ import annotations
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm, stt, tts, vad
from livekit.plugins import openai, silero
from livekit.plugins.silero.vad import _VADOptions
from livekit import rtc
from dotenv import load_dotenv
import re
import time
import json
import os
from datetime import datetime
import httpx
from openai import AsyncClient
from prompts import WELCOME_MESSAGE, INSTRUCTIONS, ASK_MESSAGE, CONFIRM_MESSAGE, REPEAT_MESSAGE, OFF_TOPIC_MESSAGE, PERMISSION_MESSAGE
load_dotenv()

# Campos a recolectar, inspirados en full_agent.py
FIELDS = [
    ("nombre_operador", "nombre completo"),
    ("numero_tractor", "número de tractor"),
    ("placas_tractor", "placas de tractor"),
    ("numero_trailer", "número de tráiler"),
    ("placas_trailer", "placas de tráiler")
]
FIELD_ORDER = [k for k, _ in FIELDS]
NUM_FIELDS = len(FIELDS)

# Detectores de repeticiones y off-topic
REPEAT_REQUESTS = {"no entendí", "repíteme", "puedes repetir", "qué dijiste", "como dijiste", "no escuché", "de nuevo", "repite", "otra vez"}
OFF_TOPIC_TRIGGERS = {"cómo estás", "qué haces", "quién eres", "qué es esto", "para qué llamas"}

def is_repeat_request(text: str) -> bool:
    text = text.lower()
    return any(trigger in text for trigger in REPEAT_REQUESTS)

def is_off_topic(text: str) -> bool:
    text = text.lower()
    return any(trigger in text for trigger in OFF_TOPIC_TRIGGERS)

# Limpieza de entrada, adaptada de clean_user_text en full_agent.py
def clean_user_text(raw: str, field: str) -> str:
    raw = raw.strip()
    if field == "nombre_operador":
        m = re.search(r"(?:mi nombre es|me llamo|soy|el nombre es)\s+(.+)", raw, re.IGNORECASE)
        name = m.group(1).strip() if m else raw
        return " ".join(p.capitalize() for p in name.split())
    elif field in ("numero_tractor", "numero_trailer"):
        digits = re.findall(r"\d", raw)
        if digits:
            return "".join(digits)
        return raw
    elif field in ("placas_tractor", "placas_trailer"):
        plate = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
        return plate
    return raw

# Función para guardar la conversación en JSON
def save_conversation_to_json(conversation_log, session_id):
    output_dir = "conversation_logs"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{output_dir}/conversation_{session_id}_{timestamp}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(conversation_log, f, ensure_ascii=False, indent=2)
    print(f"Conversation saved to {filename}")

async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    await ctx.wait_for_participant()

    # Configurar STT (Speech-to-Text) con el plugin de OpenAI
    #speech_to_text = openai.STT(
    #    model="whisper-1",
    #    language="es"
    #)
    # Configurar STT (Speech-to-Text) con OpenAI y VAD

    
     
    speech_to_text = stt.StreamAdapter(
        stt=openai.STT(
            language="es",
            model="whisper-1",
            client=AsyncClient(
                api_key=os.getenv("OPENAI_API_KEY"),
                timeout=30.0
            )
        ),
        vad=None
    )

    # Configurar LLM (GPT-4o-mini, no en tiempo real)
    language_model = openai.LLM(
        model="gpt-4o-mini",
        temperature=0.8
    )

    # Configurar TTS (Text-to-Speech) con OpenAI
    text_to_speech = openai.TTS(
        voice="shimmer",  # Voz en español, compatible con OpenAI TTS
        model="tts-1",
        client=AsyncClient(
            api_key=os.getenv('OPENAI_API_KEY'),
            timeout=30.0  # Aumentar tiempo de espera a 30 segundos
        )
    )

    # Configurar VAD (Voice Activity Detection)
    #voice_activity_detector = vad.VAD()


    session_id = str(int(time.time()))  # ID único basado en timestamp
    conversation_log = []

    # Estado inicial de la conversación
    conversation_state = {
        "state": "waiting_wake",
        "idx": 0,
        "fields": {k: None for k, _ in FIELDS},
        "route": "Ruta desconocida"
    }

    # Enviar mensaje de bienvenida
    #async for audio_chunk in text_to_speech.stream(text=WELCOME_MESSAGE):
    #    await ctx.room.local_participant.publish_audio(audio_chunk)
    
    #async for audio_chunk in text_to_speech.synthesize(WELCOME_MESSAGE):
    #    await ctx.room.local_participant.publish_audio(audio_chunk)
    # Enviar mensaje de bienvenida
    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
    await ctx.room.local_participant.publish_track(audio_track)
    async for audio_chunk in text_to_speech.synthesize(WELCOME_MESSAGE):
        # Convertir SynthesizedAudio a AudioFrame
        samples_per_channel = len(audio_chunk.frame.data) // 2
        audio_frame = rtc.AudioFrame(
            data=audio_chunk.frame.data,
            sample_rate=24000,
            num_channels=1,
            samples_per_channel=samples_per_channel
            #samples_per_channel=audio_chunk.frame.samples_per_channel
            #samples_per_channel=len(audio_chunk.frame) // 2  # Asumiendo PCM 16-bit (2 bytes por muestra)
        )
        await audio_source.capture_frame(audio_frame)
        #await audio_source.capture_frame(audio_chunk)
    
    conversation_log.append({
        "timestamp": datetime.now().isoformat(),
        "role": "assistant",
        "content": WELCOME_MESSAGE,
        "state": conversation_state["state"],
        "field": None
    })

    # Configurar el contexto de la conversación con INSTRUCTIONS
    chat_context = llm.ChatContext(messages=[
        llm.ChatMessage(role="system", content=INSTRUCTIONS)
    ])


    async def process_transcription():
        async for transcription_event in speech_to_text.stream():
            if not transcription_event.text:
                continue
            start_time = time.time()
            user_text = transcription_event.text.lower()

            # Log user input
            conversation_log.append({
                "timestamp": datetime.now().isoformat(),
                "role": "user",
                "content": user_text,
                "state": conversation_state["state"],
                "field": FIELD_ORDER[conversation_state["idx"]] if conversation_state["state"] in ["asking", "confirm"] else None
            })

            # Detectar repeticiones
            if is_repeat_request(user_text):
                current_field = FIELD_ORDER[conversation_state["idx"]]
                '''
                async for audio_chunk in text_to_speech.stream(
                    text=REPEAT_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])
                ):
                    await ctx.room.local_participant.publish_audio(audio_chunk)
                '''
                #async for audio_chunk in text_to_speech.synthesize(REPEAT_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])):
                #    await ctx.room.local_participant.publish_audio(audio_chunk)
                
                audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                await ctx.room.local_participant.publish_track(audio_track)
                async for audio_chunk in text_to_speech.synthesize(REPEAT_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])):
                    samples_per_channel = len(audio_chunk.frame.data) // 2
                    audio_frame = rtc.AudioFrame(
                    data=audio_chunk.frame.data,
                    sample_rate=24000,
                    num_channels=1,
                    samples_per_channel=samples_per_channel
                    #samples_per_channel=audio_chunk.frame.samples_per_channel
                    #samples_per_channel=len(audio_chunk.frame) // 2
                    )
                    await audio_source.capture_frame(audio_frame)
                    #await audio_source.capture_frame(audio_chunk)
                
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "system",
                    "content": REPEAT_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1]),
                    "state": conversation_state["state"],
                    "field": current_field
                })
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del sistema (repetición): {latency_ms:.2f} ms")
                continue

            # Detectar respuestas fuera de tema
            if is_off_topic(user_text):
                current_field = FIELD_ORDER[conversation_state["idx"]]
                '''
                async for audio_chunk in text_to_speech.stream(
                    text=OFF_TOPIC_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])
                ):
                    await ctx.room.local_participant.publish_audio(audio_chunk)
                '''
                #async for audio_chunk in text_to_speech.synthesize(OFF_TOPIC_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])):
                #    await ctx.room.local_participant.publish_audio(audio_chunk)
                audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                await ctx.room.local_participant.publish_track(audio_track)
                async for audio_chunk in text_to_speech.synthesize(OFF_TOPIC_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])):
                    samples_per_channel = len(audio_chunk.frame.data) // 2
                    audio_frame = rtc.AudioFrame(
                        data=audio_chunk.frame.data,
                        sample_rate=24000,
                        num_channels=1,
                        samples_per_channel=samples_per_channel
                        #samples_per_channel=audio_chunk.frame.samples_per_channel
                        #samples_per_channel=len(audio_chunk.frame) // 2
                    )
                    await audio_source.capture_frame(audio_frame)
                    #await audio_source.capture_frame(audio_chunk)
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "system",
                    "content": OFF_TOPIC_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1]),
                    "state": conversation_state["state"],
                    "field": current_field
                })
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del sistema (off-topic): {latency_ms:.2f} ms")
                continue

            # Manejo de estados
            if conversation_state["state"] == "waiting_wake":
                wake_words = {"hola", "bueno", "quién es", "quien es", "daisy"}
                if any(user_text.startswith(w) for w in wake_words):
                    conversation_state["state"] = "waiting_permission"
                    '''
                    async for audio_chunk in text_to_speech.stream(
                        text="¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"
                    ):
                        await ctx.room.local_participant.publish_audio(audio_chunk)
                    '''
                    #async for audio_chunk in text_to_speech.synthesize("¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                    await ctx.room.local_participant.publish_track(audio_track)
                    async for audio_chunk in text_to_speech.synthesize("¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"):
                        samples_per_channel = len(audio_chunk.frame.data) // 2
                        audio_frame = rtc.AudioFrame(
                            data=audio_chunk.frame.data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel = samples_per_channel
                            #samples_per_channel=audio_chunk.frame.samples_per_channel
                            #samples_per_channel=len(audio_chunk.frame) // 2
                        )
                        await audio_source.capture_frame(audio_frame)
                        #await audio_source.capture_frame(audio_chunk)
                    
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "assistant",
                        "content": "¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?",
                        "state": conversation_state["state"],
                        "field": None
                    })
                    end_time = time.time()
                    latency_ms = (end_time - start_time) * 1000
                    print(f"Latencia del sistema (wake): {latency_ms:.2f} ms")
                continue

            elif conversation_state["state"] == "waiting_permission":
                # Clasificar intención con LLM
                permission_prompt = PERMISSION_MESSAGE.format(text=user_text)
                chat_context.append(llm.ChatMessage(role="system", content=permission_prompt))
                response = await language_model.chat(messages=chat_context.messages)
                intent = response.choices[0].message.content  # Asumimos que el LLM devuelve la intención
                chat_context.append(llm.ChatMessage(role="assistant", content=intent))
                #response = await language_model.chat(
                #    messages=[llm.ChatMessage(role="system", content=permission_prompt)]
                #)
                #intent = response.choices[0].message.content  # Asumimos que el LLM devuelve la intención

                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "system",
                    "content": permission_prompt,
                    "state": conversation_state["state"],
                    "field": None
                })

                if intent == "aceptar_llamada":
                    conversation_state["state"] = "asking"
                    current_field = FIELD_ORDER[conversation_state["idx"]]
                    ask_message = ASK_MESSAGE.format(
                        field_name=FIELDS[conversation_state["idx"]][1],
                        remaining=NUM_FIELDS - conversation_state["idx"]
                    )
                    
                    #async for audio_chunk in text_to_speech.stream(text=ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    #async for audio_chunk in text_to_speech.synthesize(ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                    await ctx.room.local_participant.publish_track(audio_track)
                    async for audio_chunk in text_to_speech.synthesize(ask_message):
                        #await audio_source.capture_frame(audio_chunk)
                        samples_per_channel = len(audio_chunk.frame.data) // 2
                        audio_frame = rtc.AudioFrame(
                            data=audio_chunk.frame.data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel=samples_per_channel
                            #samples_per_channel=audio_chunk.frame.samples_per_channel
                            #samples_per_channel=len(audio_chunk.frame) // 2
                        )
                        await audio_source.capture_frame(audio_frame)
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "assistant",
                        "content": ask_message,
                        "state": conversation_state["state"],
                        "field": current_field
                    })
                elif intent == "rechazar_llamada":
                    end_message = "Entendido. Te contacto luego. ¡Échale un ojo a la ruta!"
                    #async for audio_chunk in text_to_speech.stream(text=end_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    #async for audio_chunk in text_to_speech.synthesize(end_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                    await ctx.room.local_participant.publish_track(audio_track)
                    async for audio_chunk in text_to_speech.synthesize(end_message):
                        samples_per_channel = len(audio_chunk.frame.data) // 2
                        audio_frame = rtc.AudioFrame(
                            data=audio_chunk.frame.data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel=samples_per_channel
                            #samples_per_channel=audio_chunk.frame.samples_per_channel
                            #samples_per_channel=len(audio_chunk.frame) // 2
                        )
                        await audio_source.capture_frame(audio_frame)
                        #await audio_source.capture_frame(audio_chunk)
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "assistant",
                        "content": end_message,
                        "state": conversation_state["state"],
                        "field": None
                    })
                    conversation_state["state"] = "ended"
                    save_conversation_to_json(conversation_log, session_id)
                    break
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del sistema (permission): {latency_ms:.2f} ms")
                continue

            elif conversation_state["state"] == "asking":
                current_field = FIELD_ORDER[conversation_state["idx"]]
                cleaned = clean_user_text(user_text, current_field)
                if cleaned.lower() not in {"sí", "si", "no", "correcto", "incorrecto"}:
                    conversation_state["fields"][current_field] = cleaned
                    conversation_state["state"] = "confirm"
                    confirm_message = CONFIRM_MESSAGE.format(
                        field_name=FIELDS[conversation_state["idx"]][1],
                        value=cleaned
                    )
                    #async for audio_chunk in text_to_speech.stream(text=confirm_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    #async for audio_chunk in text_to_speech.synthesize(confirm_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                    await ctx.room.local_participant.publish_track(audio_track)
                    async for audio_chunk in text_to_speech.synthesize(confirm_message):
                        samples_per_channel = len(audio_chunk.frame.data) // 2
                        audio_frame = rtc.AudioFrame(
                            data=audio_chunk.frame.data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel=samples_per_channel
                            #samples_per_channel=audio_chunk.frame.samples_per_channel
                            #samples_per_channel=len(audio_chunk.frame) // 2
                        )
                        await audio_source.capture_frame(audio_frame)
                        #await audio_source.capture_frame(audio_chunk)
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "system",
                        "content": confirm_message,
                        "state": conversation_state["state"],
                        "field": current_field
                    })
                else:
                    ask_message = ASK_MESSAGE.format(
                        field_name=FIELDS[conversation_state["idx"]][1],
                        remaining=NUM_FIELDS - conversation_state["idx"]
                    )
                    #async for audio_chunk in text_to_speech.stream(text=ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    #async for audio_chunk in text_to_speech.synthesize(ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                    await ctx.room.local_participant.publish_track(audio_track)
                    async for audio_chunk in text_to_speech.synthesize(ask_message):
                        samples_per_channel = len(audio_chunk.frame.data) // 2
                        audio_frame = rtc.AudioFrame(
                            data=audio_chunk.frame.data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel=samples_per_channel
                            #samples_per_channel=audio_chunk.frame.samples_per_channel
                            #samples_per_channel=len(audio_chunk.frame) // 2
                        )
                        await audio_source.capture_frame(audio_frame)
                        #await audio_source.capture_frame(audio_chunk)
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "assistant",
                        "content": ask_message,
                        "state": conversation_state["state"],
                        "field": current_field
                    })
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del sistema (asking): {latency_ms:.2f} ms")
                continue

            elif conversation_state["state"] == "confirm":
                if user_text.lower() not in {"no", "incorrecto"}:
                    conversation_state["idx"] += 1
                    if conversation_state["idx"] >= NUM_FIELDS:
                        end_message = "¡Gracias por los datos! Todo listo, ¡buen viaje!"
                        #async for audio_chunk in text_to_speech.stream(text=end_message):
                        #    await ctx.room.local_participant.publish_audio(audio_chunk)
                        #async for audio_chunk in text_to_speech.synthesize(end_message):
                        #    await ctx.room.local_participant.publish_audio(audio_chunk)
                        audio_source = rtc.AudioSource()
                        audio_track = rtc.AudioTrack.create_track("tts_audio", source=audio_source)
                        await ctx.room.local_participant.publish_track(audio_track)
                        async for audio_chunk in text_to_speech.synthesize(end_message):
                            samples_per_channel = len(audio_chunk.frame.data) // 2
                            audio_frame = rtc.AudioFrame(
                                data=audio_chunk.frame.data,
                                sample_rate=24000,
                                num_channels=1,
                                samples_per_channel=samples_per_channel
                                #samples_per_channel=audio_chunk.frame.samples_per_channel
                                #samples_per_channel=len(audio_chunk.frame) // 2
                            )
                            await audio_source.capture_frame(audio_frame)
                            #await audio_source.capture_frame(audio_chunk)
                        conversation_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "role": "assistant",
                            "content": end_message,
                            "state": conversation_state["state"],
                            "field": None
                        })
                        conversation_state["state"] = "ended"
                        conversation_log.append({
                            "timestamp": datetime.now().isoformat(),
                            "role": "system",
                            "content": f"Collected fields: {conversation_state['fields']}",
                            "state": conversation_state["state"],
                            "field": None
                        })
                        save_conversation_to_json(conversation_log, session_id)
                        break
                    conversation_state["state"] = "asking"
                    ask_message = ASK_MESSAGE.format(
                        field_name=FIELDS[conversation_state["idx"]][1],
                        remaining=NUM_FIELDS - conversation_state["idx"]
                    )
                    #async for audio_chunk in text_to_speech.stream(text=ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    #async for audio_chunk in text_to_speech.synthesize(ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                    await ctx.room.local_participant.publish_track(audio_track)
                    async for audio_chunk in text_to_speech.synthesize(ask_message):
                        samples_per_channel = len(audio_chunk.frame.data) // 2
                        audio_frame = rtc.AudioFrame(
                            data=audio_chunk.frame.data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel=samples_per_channel
                            #samples_per_channel=audio_chunk.frame.samples_per_channel
                            #samples_per_channel=len(audio_chunk.frame) // 2
                        )
                        await audio_source.capture_frame(audio_frame)
                        #await audio_source.capture_frame(audio_chunk)
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "assistant",
                        "content": ask_message,
                        "state": conversation_state["state"],
                        "field": FIELD_ORDER[conversation_state["idx"]]
                    })
                else:
                    conversation_state["fields"][FIELD_ORDER[conversation_state["idx"]]] = None
                    conversation_state["state"] = "asking"
                    ask_message = ASK_MESSAGE.format(
                        field_name=FIELDS[conversation_state["idx"]][1],
                        remaining=NUM_FIELDS - conversation_state["idx"]
                    )
                    #async for audio_chunk in text_to_speech.stream(text=ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    #async for audio_chunk in text_to_speech.synthesize(ask_message):
                    #    await ctx.room.local_participant.publish_audio(audio_chunk)
                    audio_source = rtc.AudioSource(sample_rate=24000, num_channels=1)
                    audio_track = rtc.LocalAudioTrack.create_audio_track("tts_audio", source=audio_source)
                    await ctx.room.local_participant.publish_track(audio_track)
                    async for audio_chunk in text_to_speech.synthesize(ask_message):
                        samples_per_channel = len(audio_chunk.frame.data) // 2
                        audio_frame = rtc.AudioFrame(
                            data=audio_chunk.frame.data,
                            sample_rate=24000,
                            num_channels=1,
                            samples_per_channel=samples_per_channel
                            #samples_per_channel=audio_chunk.frame.samples_per_channel
                            #samples_per_channel=len(audio_chunk.frame.samples_per_channel) // 2
                        )
                        await audio_source.capture_frame(audio_frame)
                        #await audio_source.capture_frame(audio_chunk)
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "assistant",
                        "content": ask_message,
                        "state": conversation_state["state"],
                        "field": FIELD_ORDER[conversation_state["idx"]]
                    })
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del sistema (confirm): {latency_ms:.2f} ms")

    # Iniciar el procesamiento de transcripciones
    try:
        await process_transcription()
    except Exception as e:
        print(f"Error en el procesamiento: {e}")
        conversation_log.append({
            "timestamp": datetime.now().isoformat(),
            "role": "system",
            "content": f"Error: {str(e)}",
            "state": conversation_state["state"],
            "field": None
        })
        save_conversation_to_json(conversation_log, session_id)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
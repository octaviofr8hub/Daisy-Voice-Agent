from __future__ import annotations
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
from dotenv import load_dotenv
from api import AssistantFnc
from daisy_prompts import WELCOME_MESSAGE, INSTRUCTIONS, ASK_MESSAGE, CONFIRM_MESSAGE, REPEAT_MESSAGE, OFF_TOPIC_MESSAGE, PERMISSION_MESSAGE
import re
import time
import json
import os
from datetime import datetime

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
        # Simplificamos: solo dígitos, sin parse_number
        return raw
    elif field in ("placas_tractor", "placas_trailer"):
        # Simplificamos: extraemos alfanuméricos y convertimos a mayúsculas
        plate = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
        return plate
    return raw

# Function to save conversation to JSON
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
    
    model = openai.realtime.RealtimeModel(  
        model="gpt-4o-realtime-preview",
        instructions=INSTRUCTIONS,
        voice="shimmer",
        temperature=0.8,
        modalities=["audio", "text"]
    )
    assistant_fnc = AssistantFnc()
    assistant = MultimodalAgent(model=model, fnc_ctx=assistant_fnc)
    
    # Workaround para errores de playout
    def _on_playout_started(*args, **kwargs):
        pass
    def _on_playout_stopped(*args, **kwargs):
        pass
    assistant._on_playout_started = _on_playout_started
    assistant._on_playout_stopped = _on_playout_stopped
    
    assistant.start(ctx.room)
    
    session = model.sessions[0]
    
    session_id = str(int(time.time()))  # Unique session ID based on timestamp
    conversation_log = []
    
    # Estado inicial de la conversación
    conversation_state = {
        "state": "waiting_wake",
        "idx": 0,
        "fields": {k: None for k, _ in FIELDS},
        "route": "Ruta desconocida"  # Placeholder, puede venir de ctx
    }
    
    # Enviar mensaje de bienvenida
    session.conversation.item.create(
        llm.ChatMessage(
            role="assistant",
            content=WELCOME_MESSAGE
        )
    )
    conversation_log.append({
        "timestamp": datetime.now().isoformat(),
        "role": "assistant",
        "content": WELCOME_MESSAGE,
        "state": conversation_state["state"],
        "field": None
    })
    session.response.create()
    
    @session.on("user_speech_committed")
    async def on_user_speech_committed(msg: llm.ChatMessage):
        start_time = time.time()  # Tiempo de inicio: cuando se recibe el audio
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
        
        user_text = msg.content.lower()
        
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
            session.conversation.item.create(
                llm.ChatMessage(
                    role="system",
                    content=REPEAT_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])
                )
            )
            conversation_log.append({
                "timestamp": datetime.now().isoformat(),
                "role": "system",
                "content": REPEAT_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1]),
                "state": conversation_state["state"],
                "field": current_field
            })
            session.response.create()
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            print(f"Latencia del LLM (repetición): {latency_ms:.2f} ms")
            return
        
        # Detectar respuestas fuera de tema
        if is_off_topic(user_text):
            current_field = FIELD_ORDER[conversation_state["idx"]]
            session.conversation.item.create(
                llm.ChatMessage(
                    role="system",
                    content=OFF_TOPIC_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1])
                )
            )
            conversation_log.append({
                "timestamp": datetime.now().isoformat(),
                "role": "system",
                "content": OFF_TOPIC_MESSAGE.format(field_name=FIELDS[conversation_state["idx"]][1]),
                "state": conversation_state["state"],
                "field": current_field
            })
            session.response.create()
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            print(f"Latencia del LLM (off-topic): {latency_ms:.2f} ms")
            return
        
        # Manejo de estados
        if conversation_state["state"] == "waiting_wake":
            # Wake words para iniciar
            wake_words = {"hola", "bueno", "quién es", "quien es", "daisy"}
            if any(user_text.startswith(w) for w in wake_words):
                conversation_state["state"] = "waiting_permission"
                session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content="¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"
                    )
                )
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "assistant",
                    "content": "¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?",
                    "state": conversation_state["state"],
                    "field": None
                })
                session.response.create()
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del LLM (wake): {latency_ms:.2f} ms")
            return
        
        elif conversation_state["state"] == "waiting_permission":
            # Clasificar intención
            permission_prompt = PERMISSION_MESSAGE.format(text=msg.content)
            session.conversation.item.create(
                llm.ChatMessage(
                    role="system",
                    content=permission_prompt
                )
            )
            conversation_log.append({
                "timestamp": datetime.now().isoformat(),
                "role": "system",
                "content": permission_prompt,
                "state": conversation_state["state"],
                "field": None
            })
            # Simulamos respuesta del modelo (en la vida real, esperaríamos la respuesta)
            intent = "aceptar_llamada"  # Placeholder, debe venir del modelo
            if intent == "aceptar_llamada":
                conversation_state["state"] = "asking"
                current_field = FIELD_ORDER[conversation_state["idx"]]
                ask_message = ASK_MESSAGE.format(
                    field_name=FIELDS[conversation_state["idx"]][1],
                    remaining=NUM_FIELDS - conversation_state["idx"]
                )
                session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content=ASK_MESSAGE.format(
                            field_name=FIELDS[conversation_state["idx"]][1],
                            remaining=NUM_FIELDS - conversation_state["idx"]
                        )
                    )
                )
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "assistant",
                    "content": ask_message,
                    "state": conversation_state["state"],
                    "field": current_field
                })
                session.response.create()
            elif intent == "rechazar_llamada":
                end_message = "Entendido. Te contacto luego. ¡Échale un ojo a la ruta!"
                session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content="Entendido. Te contacto luego. ¡Échale un ojo a la ruta!"
                    )
                )
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "assistant",
                    "content": end_message,
                    "state": conversation_state["state"],
                    "field": None
                })
                session.response.create()
                # Finalizar llamada
                conversation_state["state"] = "ended"
            # Otros casos (correo, whatsapp, etc.) se pueden agregar
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            print(f"Latencia del LLM (wake): {latency_ms:.2f} ms")
            return
        
        elif conversation_state["state"] == "asking":
            current_field = FIELD_ORDER[conversation_state["idx"]]
            cleaned = clean_user_text(msg.content, current_field)
            if cleaned.lower() not in {"sí", "si", "no", "correcto", "incorrecto"}:
                conversation_state["fields"][current_field] = cleaned
                conversation_state["state"] = "confirm"
                confirm_message = CONFIRM_MESSAGE.format(
                    field_name=FIELDS[conversation_state["idx"]][1],
                    value=cleaned
                )
                session.conversation.item.create(
                    llm.ChatMessage(
                        role="system",
                        content=CONFIRM_MESSAGE.format(
                            field_name=FIELDS[conversation_state["idx"]][1],
                            value=cleaned
                        )
                    )
                )
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "system",
                    "content": confirm_message,
                    "state": conversation_state["state"],
                    "field": current_field
                })
                session.response.create()
            else:
                ask_message = ASK_MESSAGE.format(
                    field_name=FIELDS[conversation_state["idx"]][1],
                    remaining=NUM_FIELDS - conversation_state["idx"]
                )
                # Repetir pregunta si la respuesta no es válida
                session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content=ASK_MESSAGE.format(
                            field_name=FIELDS[conversation_state["idx"]][1],
                            remaining=NUM_FIELDS - conversation_state["idx"]
                        )
                    )
                )
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "assistant",
                    "content": ask_message,
                    "state": conversation_state["state"],
                    "field": current_field
                })
                session.response.create()
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            print(f"Latencia del LLM (wake): {latency_ms:.2f} ms")
            return
        
        elif conversation_state["state"] == "confirm":
            # Simplificamos: asumimos confirmación si no es negativa
            if user_text.lower() not in {"no", "incorrecto"}:
                conversation_state["idx"] += 1
                if conversation_state["idx"] >= NUM_FIELDS:
                    session.conversation.item.create(
                        llm.ChatMessage(
                            role="assistant",
                            content="¡Gracias por los datos! Todo listo, ¡buen viaje!"
                        )
                    )
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "assistant",
                        "content": end_message,
                        "state": conversation_state["state"],
                        "field": None
                    })
                    session.response.create()
                    conversation_state["state"] = "ended"
                    conversation_log.append({
                        "timestamp": datetime.now().isoformat(),
                        "role": "system",
                        "content": f"Collected fields: {conversation_state['fields']}",
                        "state": conversation_state["state"],
                        "field": None
                    })
                    save_conversation_to_json(conversation_log, session_id)
                    return
                conversation_state["state"] = "asking"
                ask_message = ASK_MESSAGE.format(
                    field_name=FIELDS[conversation_state["idx"]][1],
                    remaining=NUM_FIELDS - conversation_state["idx"]
                )
                session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content=ASK_MESSAGE.format(
                            field_name=FIELDS[conversation_state["idx"]][1],
                            remaining=NUM_FIELDS - conversation_state["idx"]
                        )
                    )
                )
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "assistant",
                    "content": ask_message,
                    "state": conversation_state["state"],
                    "field": FIELD_ORDER[conversation_state["idx"]]
                })
                session.response.create()
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del LLM (wake): {latency_ms:.2f} ms")
            else:
                conversation_state["fields"][FIELD_ORDER[conversation_state["idx"]]] = None
                conversation_state["state"] = "asking"
                ask_message = ASK_MESSAGE.format(
                    field_name=FIELDS[conversation_state["idx"]][1],
                    remaining=NUM_FIELDS - conversation_state["idx"]
                )
                session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content=ASK_MESSAGE.format(
                            field_name=FIELDS[conversation_state["idx"]][1],
                            remaining=NUM_FIELDS - conversation_state["idx"]
                        )
                    )
                )
                conversation_log.append({
                    "timestamp": datetime.now().isoformat(),
                    "role": "assistant",
                    "content": ask_message,
                    "state": conversation_state["state"],
                    "field": FIELD_ORDER[conversation_state["idx"]]
                })
                session.response.create()
                end_time = time.time()
                latency_ms = (end_time - start_time) * 1000
                print(f"Latencia del LLM (wake): {latency_ms:.2f} ms")
    
    # Manejar mensajes de texto (lk.chat)
    @assistant.on("text_stream")
    async def on_text_stream(msg: llm.ChatMessage):
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
        await on_user_speech_committed(msg)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
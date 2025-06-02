from livekit.agents import llm
from config import FIELDS, FIELD_ORDER, NUM_FIELDS, WAKE_WORDS
from utils import clean_user_text, is_repeat_request, is_off_topic
from daisy_prompts import WELCOME_MESSAGE, ASK_MESSAGE, CONFIRM_MESSAGE, REPEAT_MESSAGE, OFF_TOPIC_MESSAGE, PERMISSION_MESSAGE
from logger import ConversationLogger
import time

# Clase que maneja la máquina de estados de la conversación
class ConversationStateMachine:
    def __init__(self, session, logger: ConversationLogger):
        # Almacena la sesión de LiveKit
        self.session = session
        # Almacena el logger para registrar la conversación
        self.logger = logger
        # Estado inicial de la conversación
        self.state = {
            "state": "waiting_wake",
            "idx": 0,
            "fields": {k: None for k, _ in FIELDS},
            "route": "Ruta desconocida"
        }

    async def send_welcome(self):
        """
        Envía el mensaje de bienvenida y lo registra
        """
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="assistant",
                content=WELCOME_MESSAGE
            )
        )
        self.logger.log_message("assistant", WELCOME_MESSAGE, self.state["state"])
        self.session.response.create()

    async def process_user_input(self, msg: llm.ChatMessage):
        """
        Procesa la entrada del usuario
        """
        start_time = time.time()
        # Convierte el contenido del mensaje si es una lista
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
        
        user_text = msg.content
        user_text_lower = user_text.lower()
        # Registra la entrada del usuario
        current_field = FIELD_ORDER[self.state["idx"]] if self.state["state"] in ["asking", "confirm"] else None
        self.logger.log_message("user", user_text, self.state["state"], current_field)

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
        print(f"Latencia del LLM ({self.state['state']}): {latency_ms:.2f} ms")

    # Maneja solicitudes de repetición
    async def handle_repeat(self):
        current_field = FIELD_ORDER[self.state["idx"]]
        repeat_message = REPEAT_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=repeat_message
            )
        )
        self.logger.log_message("system", repeat_message, self.state["state"], current_field)
        self.session.response.create()

    # Maneja respuestas fuera de tema
    async def handle_off_topic(self):
        current_field = FIELD_ORDER[self.state["idx"]]
        off_topic_message = OFF_TOPIC_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=off_topic_message
            )
        )
        self.logger.log_message("system", off_topic_message, self.state["state"], current_field)
        self.session.response.create()

    # Maneja el estado waiting_wake
    async def handle_waiting_wake(self, user_text_lower: str):
        if any(user_text_lower.startswith(w) for w in WAKE_WORDS):
            self.state["state"] = "waiting_permission"
            permission_request = "¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=permission_request
                )
            )
            self.logger.log_message("assistant", permission_request, self.state["state"])
            self.session.response.create()

    # Maneja el estado waiting_permission
    async def handle_waiting_permission(self, user_text: str):
        permission_prompt = PERMISSION_MESSAGE.format(text=user_text)
        self.session.conversation.item.create(
            llm.ChatMessage(
                role="system",
                content=permission_prompt
            )
        )
        self.logger.log_message("system", permission_prompt, self.state["state"])
        intent = "aceptar_llamada"  # Placeholder, debe venir del modelo
        if intent == "aceptar_llamada":
            self.state["state"] = "asking"
            current_field = FIELD_ORDER[self.state["idx"]]
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
            self.logger.log_message("assistant", ask_message, self.state["state"], current_field)
            self.session.response.create()
        elif intent == "rechazar_llamada":
            end_message = "Entendido. Te contacto luego. ¡Échale un ojo a la ruta!"
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="assistant",
                    content=end_message
                )
            )
            self.logger.log_message("assistant", end_message, self.state["state"])
            self.state["state"] = "ended"
            self.logger.log_message("system", f"Collected fields: {self.state['fields']}", self.state["state"])
            self.logger.save()

    # Maneja el estado asking
    async def handle_asking(self, user_text: str):
        current_field = FIELD_ORDER[self.state["idx"]]
        cleaned = clean_user_text(user_text, current_field)
        if cleaned.lower() not in {"sí", "si", "no", "correcto", "incorrecto"}:
            self.state["fields"][current_field] = cleaned
            self.state["state"] = "confirm"
            confirm_message = CONFIRM_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                value=cleaned
            )
            self.session.conversation.item.create(
                llm.ChatMessage(
                    role="system",
                    content=confirm_message
                )
            )
            self.logger.log_message("system", confirm_message, self.state["state"], current_field)
            self.session.response.create()
        else:
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
            self.logger.log_message("assistant", ask_message, self.state["state"], current_field)
            self.session.response.create()

    # Maneja el estado confirm
    async def handle_confirm(self, user_text_lower: str):
        if user_text_lower not in {"no", "incorrecto"}:
            self.state["idx"] += 1
            if self.state["idx"] >= NUM_FIELDS:
                end_message = "¡Gracias por los datos! Todo listo, ¡buen viaje!"
                self.session.conversation.item.create(
                    llm.ChatMessage(
                        role="assistant",
                        content=end_message
                    )
                )
                self.logger.log_message("assistant", end_message, self.state["state"])
                self.state["state"] = "ended"
                self.logger.log_message("system", f"Collected fields: {self.state['fields']}", self.state["state"])
                self.logger.save()
                return
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
            self.logger.log_message("assistant", ask_message, self.state["state"], FIELD_ORDER[self.state["idx"]])
            self.session.response.create()
        else:
            self.state["fields"][FIELD_ORDER[self.state["idx"]]] = None
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
            self.logger.log_message("assistant", ask_message, self.state["state"], FIELD_ORDER[self.state["idx"]])
            self.session.response.create()
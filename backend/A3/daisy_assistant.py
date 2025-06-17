'''
import json
import os
import asyncio
from datetime import datetime
from config import FIELDS, FIELD_ORDER, NUM_FIELDS, WAKE_WORDS
from prompts import WELCOME_MESSAGE, ASK_MESSAGE, CONFIRM_MESSAGE, REPEAT_MESSAGE, OFF_TOPIC_MESSAGE, PERMISSION_MESSAGE
from utils import clean_user_text, is_repeat_request, is_off_topic, infer_plate_from_text, infer_eta_from_text
from details_templates import DriverDetails, TractorDetails, TrailerDetails, ETADetails
import logging

logger = logging.getLogger(__name__)

class DaisyAssistant:
    def __init__(self, session_id):
        self.session_id = session_id
        self.state = {
            "state": "waiting_wake",
            "idx": 0,
            "fields": {k: None for k, _ in FIELDS},
            "confirmation_attempts": 0
        }
        self.conversation_log = []
        self.driver_details = {DriverDetails.NOMBRE_OPERADOR: ""}
        self.tractor_details = {TractorDetails.NUMERO_TRACTOR: "", TractorDetails.PLACAS_TRACTOR: ""}
        self.trailer_details = {TrailerDetails.NUMERO_TRAILER: "", TrailerDetails.PLACAS_TRAILER: ""}
        self.eta_details = {ETADetails.ETA: ""}
        logger.info(f"Initialized DaisyAssistant with SessionID={session_id}")

    def _log_message(self, role: str, content: str):
        """Log a message to the conversation history."""
        self.conversation_log.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": str(content)
        })

    def _save_to_json(self):
        """Save collected data and conversation log to JSON."""
        try:
            output_dir = "conversation_logs"
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{output_dir}/conversation_{self.session_id}_{timestamp}.json"
            data = {
                "session_id": self.session_id,
                "driver_details": {k.value: v for k, v in self.driver_details.items()},
                "tractor_details": {k.value: v for k, v in self.tractor_details.items()},
                "trailer_details": {k.value: v for k, v in self.trailer_details.items()},
                "eta_details": {k.value: v for k, v in self.eta_details.items()},
                "conversation_log": self.conversation_log
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved conversation log to {filename}")
        except Exception as e:
            logger.error(f"Error saving JSON: {str(e)}")

    async def get_welcome_message(self):
        """Generate welcome message."""
        self._log_message("assistant", WELCOME_MESSAGE)
        return "¡Hola, qué tal! Soy Daisy, estoy aquí para ayudarte con tu registro de carrier. ¿Me das tu nombre completo, porfa?"

    async def process_user_input(self, user_text: str, openai_client):
        """Process user input and return the next response."""
        user_text_lower = user_text.lower().strip()
        self._log_message("user", user_text)
        logger.debug(f"State: {self.state['state']}, Input: {user_text}")

        if is_repeat_request(user_text_lower):
            logger.debug(f"Detected repeat request")
            return await self._handle_repeat()
        elif is_off_topic(user_text_lower):
            logger.debug(f"Detected off-topic input")
            return await self._handle_off_topic()
        elif self.state["state"] == "waiting_wake":
            logger.debug(f"Handling waiting_wake")
            return await self._handle_waiting_wake(user_text_lower)
        elif self.state["state"] == "waiting_permission":
            logger.debug(f"Handling waiting_permission")
            return await self._handle_waiting_permission(user_text, openai_client)
        elif self.state["state"] == "asking":
            logger.debug(f"Handling asking")
            return await self._handle_asking(user_text, openai_client)
        elif self.state["state"] == "confirm":
            logger.debug(f"Handling confirm")
            return await self._handle_confirm(user_text_lower)

    async def _handle_repeat(self):
        """Handle repeat request."""
        message = REPEAT_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        self._log_message("assistant", message)
        return {"status": "continue", "message": message}

    async def _handle_off_topic(self):
        """Handle off-topic response."""
        message = OFF_TOPIC_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        self._log_message("assistant", message)
        return {"status": "continue", "message": message}

    async def _handle_waiting_wake(self, user_text_lower: str):
        """Handle waiting for wake word."""
        if any(user_text_lower.startswith(w) for w in WAKE_WORDS):
            self.state["state"] = "waiting_permission"
            message = "¡Hola, qué tal! Soy Daisy, necesito unos datos para tu registro. ¿Puedo hacerte unas preguntas?"
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}
        return {"status": "continue", "message": "Por favor, di 'hola' o 'Daisy' para comenzar."}

    async def _handle_waiting_permission(self, user_text: str, openai_client):
        """Handle permission to continue call."""
        logger.info(f"Skipping OpenAI, assuming aceptar_llamada for input: {user_text}")
        self.state["state"] = "asking"
        message = ASK_MESSAGE.format(
            field_name=FIELDS[self.state["idx"]][1],
            remaining=NUM_FIELDS - self.state["idx"]
        )
        self._log_message("assistant", message)
        return {"status": "continue", "message": message}

    async def _handle_asking(self, user_text: str, openai_client):
        """Handle asking for data."""
        current_field = FIELD_ORDER[self.state["idx"]]
        cleaned = clean_user_text(user_text, current_field)

        if cleaned.lower() in {"sí", "si", "no", "correcto", "incorrecto"}:
            message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}

        try:
            if current_field == "nombre_operador":
                self.driver_details[DriverDetails.NOMBRE_OPERADOR] = cleaned.title()
            elif current_field == "numero_tractor":
                self.tractor_details[TractorDetails.NUMERO_TRACTOR] = cleaned
            elif current_field == "placas_tractor":
                plate = await infer_plate_from_text(cleaned, openai_client)
                if not plate:
                    message = ASK_MESSAGE.format(
                        field_name=FIELDS[self.state["idx"]][1],
                        remaining=NUM_FIELDS - self.state["idx"]
                    )
                    self._log_message("assistant", message)
                    return {"status": "continue", "message": message}
                self.tractor_details[TractorDetails.PLACAS_TRACTOR] = plate
                cleaned = plate
            elif current_field == "numero_trailer":
                self.trailer_details[TrailerDetails.NUMERO_TRAILER] = cleaned
            elif current_field == "placas_trailer":
                plate = await infer_plate_from_text(cleaned, openai_client)
                if not plate:
                    message = ASK_MESSAGE.format(
                        field_name=FIELDS[self.state["idx"]][1],
                        remaining=NUM_FIELDS - self.state["idx"]
                    )
                    self._log_message("assistant", message)
                    return {"status": "continue", "message": message}
                self.trailer_details[TrailerDetails.PLACAS_TRAILER] = plate
                cleaned = plate
            elif current_field == "eta":
                eta = await infer_eta_from_text(cleaned, openai_client)
                if not eta:
                    message = ASK_MESSAGE.format(
                        field_name=FIELDS[self.state["idx"]][1],
                        remaining=NUM_FIELDS - self.state["idx"]
                    )
                    self._log_message("assistant", message)
                    return {"status": "continue", "message": message}
                self.eta_details[ETADetails.ETA] = eta
                cleaned = eta
        except Exception as e:
            logger.error(f"Error processing field {current_field}: {str(e)}")
            message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}

        self.state["fields"][current_field] = cleaned
        self.state["state"] = "confirm"
        self.state["confirmation_attempts"] = 0
        confirm_message = CONFIRM_MESSAGE.format(
            field_name=FIELDS[self.state["idx"]][1],
            value=" ".join(cleaned) if current_field in ("placas_tractor", "placas_trailer") else cleaned
        )
        self._log_message("assistant", confirm_message)
        return {"status": "continue", "message": confirm_message}

    async def _handle_confirm(self, user_text_lower: str):
        """Handle confirmation of data."""
        current_field = FIELD_ORDER[self.state["idx"]]
        self.state["confirmation_attempts"] += 1

        if user_text_lower in {"sí", "si", "correcto", "sí está bien", "está bien"}:
            self.state["idx"] += 1
            self.state["confirmation_attempts"] = 0
            if self.state["idx"] >= NUM_FIELDS:
                self.state["state"] = "ended"
                message = "¡Gracias por los datos! Todo listo, ¡buen viaje!"
                self._save_to_json()
                self._log_message("assistant", message)
                return {"status": "ended", "message": message}
            self.state["state"] = "asking"
            message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}
        elif user_text_lower in {"no", "incorrecto", "no está bien"} or self.state["confirmation_attempts"] >= 3:
            self.state["fields"][current_field] = None
            self.state["state"] = "asking"
            message = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}
        else:
            
            confirm_message = CONFIRM_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                value=" ".join(self.state["fields"][current_field]) if current_field in ("placas_tractor", "placas_trailer") else self.state["fields"][current_field]
            )
            self._log_message("assistant", confirm_message)
            return {"status": "continue", "message": confirm_message}
'''
import json
import os
from datetime import datetime
from config import FIELDS, FIELD_ORDER, NUM_FIELDS
from prompts import WELCOME_MESSAGE, ASK_MESSAGE, CONFIRM_MESSAGE, REPEAT_MESSAGE, OFF_TOPIC_MESSAGE, PERMISSION_MESSAGE
from utils import clean_user_text, is_repeat_request, is_off_topic, infer_plate_from_text, infer_eta_from_text
from details_templates import DriverDetails, TractorDetails, TrailerDetails, ETADetails
import logging
from openai import AsyncOpenAI
import asyncio

logger = logging.getLogger(__name__)

class DaisyAssistant:
    def __init__(self, session_id):
        self.session_id = session_id
        self.state = {
            "state": "asking",  # Empezar directo en asking
            "idx": 0,
            "fields": {k: None for k, _ in FIELDS},
            "confirmation_attempts": 0
        }
        self.conversation_log = []
        self.driver_details = {DriverDetails.NOMBRE_OPERADOR: ""}
        self.tractor_details = {TractorDetails.NUMERO_TRACTOR: "", TractorDetails.PLACAS_TRACTOR: ""}
        self.trailer_details = {TrailerDetails.NUMERO_TRAILER: "", TrailerDetails.PLACAS_TRAILER: ""}
        self.eta_details = {ETADetails.ETA: ""}
        logger.info(f"Initialized DaisyAssistant with SessionID={session_id}")

    def _log_message(self, role: str, content: str):
        """Log a message to the conversation history."""
        self.conversation_log.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": str(content)
        })

    def _save_to_json(self):
        """Save collected data and conversation log to JSON."""
        try:
            output_dir = "conversation_logs"
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{output_dir}/conversation_{self.session_id}_{timestamp}.json"
            data = {
                "session_id": self.session_id,
                "driver_details": {k.value: v for k, v in self.driver_details.items()},
                "tractor_details": {k.value: v for k, v in self.tractor_details.items()},
                "trailer_details": {k.value: v for k, v in self.trailer_details.items()},
                "eta_details": {k.value: v for k, v in self.eta_details.items()},
                "conversation_log": self.conversation_log
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved conversation log to {filename}")
        except Exception as e:
            logger.error(f"Error saving JSON: {str(e)}")

    async def get_welcome_message(self):
        """Generate welcome message."""
        self._log_message("assistant", WELCOME_MESSAGE)
        return "¡Hola, qué tal! Soy Daisy, vamos a completar tu registro. Primero, dime tu nombre completo, ¿vale?"

    async def _process_prompt(self, prompt: str, openai_client: AsyncOpenAI) -> str:
        """Process a prompt with OpenAI to generate a natural response."""
        try:
            task = openai_client.chat.completions.create(
                model="chatgpt-4o-latest",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.8
            )
            response = await asyncio.wait_for(task, timeout=5.0)
            return response.choices[0].message.content.strip()
        except asyncio.TimeoutError:
            logger.error(f"Timeout processing prompt: {prompt}")
            return "Lo siento, no pude procesar la respuesta. Vamos a intentarlo de nuevo."
        except Exception as e:
            logger.error(f"Error processing prompt: {str(e)}")
            return "Lo siento, no pude procesar la respuesta. Vamos a intentarlo de nuevo."

    async def process_user_input(self, user_text: str, openai_client: AsyncOpenAI):
        """Process user input and return the next response."""
        user_text_lower = user_text.lower().strip()
        self._log_message("user", user_text)
        logger.info(f"Processing input for SessionID={self.session_id}, State={self.state['state']}, Input={user_text}")

        if is_repeat_request(user_text_lower):
            logger.debug(f"Detected repeat request")
            return await self._handle_repeat(openai_client)
        elif is_off_topic(user_text_lower):
            logger.debug(f"Detected off-topic input")
            return await self._handle_off_topic(openai_client)
        elif self.state["state"] == "asking":
            logger.debug(f"Handling asking")
            return await self._handle_asking(user_text, openai_client)
        elif self.state["state"] == "confirm":
            logger.debug(f"Handling confirm")
            return await self._handle_confirm(user_text_lower, openai_client)
        elif self.state["state"] == "waiting_permission":
            logger.debug(f"Handling waiting_permission")
            return await self._handle_waiting_permission(user_text, openai_client)

    async def _handle_repeat(self, openai_client: AsyncOpenAI):
        """Handle repeat request."""
        prompt = REPEAT_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        message = await self._process_prompt(prompt, openai_client)
        self._log_message("assistant", message)
        return {"status": "continue", "message": message}

    async def _handle_off_topic(self, openai_client):
        """Handle off-topic response."""
        prompt = OFF_TOPIC_MESSAGE.format(field_name=FIELDS[self.state["idx"]][1])
        message = await self._process_prompt(prompt, openai_client)
        self._log_message("assistant", message)
        return {"status": "continue", "message": message}

    async def _handle_waiting_permission(self, user_text: str, openai_client):
        """Handle permission to continue call."""
        logger.info(f"Skipping OpenAI, assuming aceptar_llamada for input: {user_text}")
        self.state["state"] = "asking"
        prompt = ASK_MESSAGE.format(
            field_name=FIELDS[self.state["idx"]][1],
            remaining=NUM_FIELDS - self.state["idx"]
        )
        message = await self._process_prompt(prompt, openai_client)
        self._log_message("assistant", message)
        return {"status": "continue", "message": message}

    async def _handle_asking(self, user_text: str, openai_client):
        """Handle asking for data."""
        current_field = FIELD_ORDER[self.state["idx"]]
        cleaned = clean_user_text(user_text, current_field)

        if cleaned.lower() in {"sí", "si", "no", "correcto", "incorrecto"}:
            prompt = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            message = await self._process_prompt(prompt, openai_client)
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}

        try:
            if current_field == "nombre_operador":
                self.driver_details[DriverDetails.NOMBRE_OPERADOR] = cleaned.title()
            elif current_field == "numero_tractor":
                self.tractor_details[TractorDetails.NUMERO_TRACTOR] = cleaned
            elif current_field == "placas_tractor":
                plate = await infer_plate_from_text(cleaned, openai_client)
                if not plate:
                    prompt = ASK_MESSAGE.format(
                        field_name=FIELDS[self.state["idx"]][1],
                        remaining=NUM_FIELDS - self.state["idx"]
                    )
                    message = await self._process_prompt(prompt, openai_client)
                    self._log_message("assistant", message)
                    return {"status": "continue", "message": message}
                self.tractor_details[TractorDetails.PLACAS_TRACTOR] = plate
                cleaned = plate
            elif current_field == "numero_trailer":
                self.trailer_details[TrailerDetails.NUMERO_TRAILER] = cleaned
            elif current_field == "placas_trailer":
                plate = await infer_plate_from_text(cleaned, openai_client)
                if not plate:
                    prompt = ASK_MESSAGE.format(
                        field_name=FIELDS[self.state["idx"]][1],
                        remaining=NUM_FIELDS - self.state["idx"]
                    )
                    message = await self._process_prompt(prompt, openai_client)
                    self._log_message("assistant", message)
                    return {"status": "continue", "message": message}
                self.trailer_details[TrailerDetails.PLACAS_TRAILER] = plate
                cleaned = plate
            elif current_field == "eta":
                eta = await infer_eta_from_text(cleaned, openai_client)
                if not eta:
                    prompt = ASK_MESSAGE.format(
                        field_name=FIELDS[self.state["idx"]][1],
                        remaining=NUM_FIELDS - self.state["idx"]
                    )
                    message = await self._process_prompt(prompt, openai_client)
                    self._log_message("assistant", message)
                    return {"status": "continue", "message": message}
                self.eta_details[ETADetails.ETA] = eta
                cleaned = eta
        except Exception as e:
            logger.error(f"Error processing field {current_field}: {str(e)}")
            prompt = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            message = await self._process_prompt(prompt, openai_client)
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}

        self.state["fields"][current_field] = cleaned
        self.state["state"] = "confirm"
        self.state["confirmation_attempts"] = 0
        prompt = CONFIRM_MESSAGE.format(
            field_name=FIELDS[self.state["idx"]][1],
            value=" ".join(cleaned) if current_field in ("placas_tractor", "placas_trailer") else cleaned
        )
        confirm_message = await self._process_prompt(prompt, openai_client)
        self._log_message("assistant", confirm_message)
        return {"status": "continue", "message": confirm_message}

    async def _handle_confirm(self, user_text_lower: str, openai_client):
        """Handle confirmation of data."""
        current_field = FIELD_ORDER[self.state["idx"]]
        self.state["confirmation_attempts"] += 1

        if user_text_lower in {"sí", "si", "correcto", "sí está bien", "está bien"}:
            self.state["idx"] += 1
            self.state["confirmation_attempts"] = 0
            if self.state["idx"] >= NUM_FIELDS:
                self.state["state"] = "ended"
                message = "¡Gracias por los datos! Todo listo, ¡buen viaje!"
                self._save_to_json()
                self._log_message("assistant", message)
                return {"status": "ended", "message": message}
            self.state["state"] = "asking"
            prompt = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            message = await self._process_prompt(prompt, openai_client)
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}
        elif user_text_lower in {"no", "incorrecto", "no está bien"} or self.state["confirmation_attempts"] >= 3:
            self.state["fields"][current_field] = None
            self.state["state"] = "asking"
            self.state["confirmation_attempts"] = 0
            prompt = ASK_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                remaining=NUM_FIELDS - self.state["idx"]
            )
            message = await self._process_prompt(prompt, openai_client)
            self._log_message("assistant", message)
            return {"status": "continue", "message": message}
        else:
            if self.state["confirmation_attempts"] >= 5:
                self.state["state"] = "ended"
                message = "Lo siento, no pude confirmar el dato. Te contacto luego, ¡échale un ojo a la ruta!"
                self._save_to_json()
                self._log_message("assistant", message)
                return {"status": "ended", "message": message}
            prompt = CONFIRM_MESSAGE.format(
                field_name=FIELDS[self.state["idx"]][1],
                value=" ".join(self.state["fields"][current_field]) if current_field in ("placas_tractor", "placas_trailer") else self.state["fields"][current_field]
            )
            confirm_message = await self._process_prompt(prompt, openai_client)
            self._log_message("assistant", confirm_message)
            return {"status": "continue", "message": confirm_message}


from __future__ import annotations
from .asi1_agent import ASI1RequestWrapper
from .utils import ( 
    infer_plate_from_text,
    normalize_letter_pronunciations
)
import logging
from dotenv import load_dotenv
from typing import (
    Any, 
    List
)
import requests
from livekit import rtc, api
import asyncio
import os
import random
from .en_prompts import ( 
    INSTRUCTIONS, 
    WELCOME_MESSAGE_ARRAY, 
    ASK_MESSAGE, 
    CONFIRM_MESSAGE, 
    REPEAT_MESSAGE, 
    OFF_TOPIC_MESSAGE, 
)
from models.driver_model import ( 
    DataField, 
    DriverData 
)
from livekit.agents import ( 
    Agent, 
    RunContext, 
    function_tool, 
    get_job_context 
)

load_dotenv(override=True)
logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

class VoiceAgent(Agent):
    def __init__(self, dial_info: dict[str, Any]):
        super().__init__(
            instructions=INSTRUCTIONS
        )
        self.participant: rtc.RemoteParticipant | None = None
        self.dial_info = dial_info
        self.transcript_log: list[str] = []  # for logging events like complaints/reschedules
        self.data = DriverData()
        self.current_field = None
        self.fields_to_collect: List[DataField] = [
            DataField.NAME,
            DataField.TRACTOR_NUMBER,
            DataField.TRACTOR_PLATES,
            DataField.TRAILER_NUMBER,
            DataField.TRAILER_PLATES,
            DataField.ETA,
            DataField.EMAIL
        ]
        self.waiting_for_confirmation = False
        self.last_value = None
        self.phone_number = None
        # Configuracion para las placas
        self.current_plate_type = None  # tractor_plates o trailer_plates
        self.in_letter_mode = False
        self.letter_index = 0
        self.partial_plate = []  
        self.say_welcome = True
        self.asi1_llm = ASI1RequestWrapper(api_key=os.getenv('ASI1_API_KEY'))

    async def on_enter(self):
        self.current_field = self.fields_to_collect[0]

    async def on_user_message(self, message: str):
        if self.in_letter_mode:
            await self._handle_letter_by_letter(message)
        elif not self.current_field:
            return
        
        if self.waiting_for_confirmation:
            await self.handle_confirmation(message)
        else:
            await self.handle_data_collection(message)

    async def handle_data_collection(self, message: str):
        # Validate input based on field
        if self.current_field in [DataField.TRACTOR_PLATES, DataField.TRAILER_PLATES]:
            self.in_letter_mode = True
            self.partial_plate = []
            self.letter_index = 0
            self.current_plate_type = self.current_field
            #await self.session.generate_reply("Vamos a hacerlo letra por letra. Dime la primera letra de la placa.")
            #await self.session.say("Vamos a hacerlo letra por letra. Dime la primera letra de la placa.")
            await self.session.say("Let's do it letter by letter. Tell me the first letter of the plate.")
            return
        if self.current_field == DataField.NAME:
            self.data.name = message
        elif self.current_field == DataField.TRACTOR_NUMBER:
            self.data.tractor_number = message
        elif self.current_field == DataField.TRAILER_NUMBER:
            self.data.trailer_number = message
        elif self.current_field == DataField.ETA:
            if not self._is_valid_eta(message):

                #await self.session.generate_reply(
                #    REPEAT_MESSAGE.format(
                #        field_name=self.current_field.value,
                #    )
                #)
                response = self.asi1_llm.generate(
                    REPEAT_MESSAGE.format(
                        field_name=self.current_field.value,
                    )
                )
                await self.session.say(response)
                return
            self.data.eta = message
        elif self.current_field == DataField.EMAIL:
            self.data.email = message

        self.last_value = message
        self.waiting_for_confirmation = True
        formatted_value = self._format_value(self.current_field, message)
        #await self.session.generate_reply(
        #    CONFIRM_MESSAGE.format(
        #        field_name=self.current_field.value, 
        #        value=formatted_value
        #    )
        #)
        response = self.asi1_llm.generate(
                CONFIRM_MESSAGE.format(
                field_name=self.current_field.value, 
                value=formatted_value
            )
        )
        await self.session.say(response)
    async def _handle_letter_by_letter(self, message: str):
        normalized = normalize_letter_pronunciations(message).replace(" ", "")
        if not normalized:
            #await self.session.say("No entendí esa letra. ¿Puedes repetirla por favor?")
            await self.session.say("I didn't catch that letter. Can you repeat it, please?")
            #await self.session.generate_reply("No entendí esa letra. ¿Puedes repetirla por favor?")
            return

        letra = normalized[0]
        self.last_value = letra
        self.waiting_for_confirmation = True
        #await self.session.generate_reply(f"¿La letra es {letra}?",)
        #await self.session.say(f"¿La letra es {letra}?")
        await self.session.say(f"Is the letter {letra}?")
    async def handle_confirmation(self, message: str):
        message = message.lower().strip()
        #if message in ["sí", "sí está bien", "correcto", "está bien", "sí, avanza"]:
        if message in ["yes", "that's right", "correct", "it's good", "yes, go ahead"]:
            self.waiting_for_confirmation = False
            if self.in_letter_mode:
                self.partial_plate.append(self.last_value)
                self.letter_index += 1
                if self.letter_index == 3:
                    #await self.session.generate_reply("Ahora vamos con los números. Dime el primer número.")
                    #await self.session.say("Ahora vamos con los números. Dime el primer número.")
                    await self.session.say("Now let's move to the numbers. Tell me the first number.")
                elif self.letter_index == 7:
                    # Arma la placa completa
                    plate_str = "".join(self.partial_plate)
                    plate = f"{plate_str[:3]}-{plate_str[3:]}"
                    if not self._is_valid_plate(plate):
                        #await self.session.generate_reply(
                        #    "Hmm, no entendí bien la placa completa. Vamos a repetir todo desde el principio. Dime la primera letra."
                        #)
                        #await self.session.say("Hmm, no entendí bien la placa completa. Vamos a repetir todo desde el principio. Dime la primera letra.")
                        await self.session.say("Hmm, I didn't quite get the full plate. Let's start over from the beginning. Tell me the first letter.")
                        self.partial_plate = []
                        self.letter_index = 0
                        return
                    if self.current_plate_type == DataField.TRACTOR_PLATES:
                        self.data.tractor_plates = plate
                    else:
                        self.data.trailer_plates = plate
                    formatted_value = self._format_value(self.current_field, plate)
                    #await self.session.generate_reply(
                    #    CONFIRM_MESSAGE.format(field_name=self.current_field.value, value=formatted_value)
                    #)
                    response = self.asi1_llm.generate(
                        CONFIRM_MESSAGE.format(
                            field_name=self.current_field.value,
                            value=formatted_value
                        )
                    )
                    await self.session.say(response)
                    self.waiting_for_confirmation = True
                    self.in_letter_mode = False
                    return
                else:
                    tipo = "letter" if self.letter_index < 3 else "number"
                    #tipo = "letra" if self.letter_index < 3 else "número"
                    await self.session.say(f"Give me the next {tipo}.")
                    #await self.session.say(f"Dame la siguiente {tipo}.")
                    #await self.session.generate_reply(f"Dame la siguiente {tipo}.")
            else:
                # avanzar al siguiente campo si la confirmacion es correcta
                self.fields_to_collect.remove(self.current_field)
                if self.fields_to_collect:
                    self.current_field = self.fields_to_collect[0]
                    remaining = len(self.fields_to_collect)
                    response = self.asi1_llm.generate(
                        ASK_MESSAGE.format(
                            field_name=self.current_field.value,
                            remaining=remaining
                        )
                    )
                    await self.session.say(response)
                else:
                    await self.save_driver_data()
                    #await self.session.say("¡Perfecto, ya tengo todos tus datos! Gracias, ¡que tengas buen viaje!")
                    await self.session.say("Perfect, I have all your info! Thanks, and have a great trip!")
                    self.current_field = None

        #elif message in ["no", "no está bien", "corrige", "incorrecto"]:
        elif message in ["no", "that's not right", "fix it", "incorrect"]:
            self.waiting_for_confirmation = False
            #await self.session.say("Ok, dime nuevamente esa letra o número.")
            await self.session.say("Okay, tell me that letter or number again.")
            #await self.session.generate_reply("Ok, dime nuevamente esa letra o número.")
        else:
            response = self.asi1_llm.generate(
                OFF_TOPIC_MESSAGE.format(field_name=self.current_field.value)
            )
            await self.session.say(response)
            #await self.session.generate_reply(
            #    OFF_TOPIC_MESSAGE.format(field_name=self.current_field.value)
            #)

    def _is_valid_plate(self, plate: str) -> bool:
        # Simple validation for plates (e.g., ABC-1234 or XY-1234)
        parts = plate.strip().split('-')
        if len(parts) != 2:
            return False
        letters, numbers = parts
        return len(letters) in [2, 3] and letters.isalpha() and len(numbers) == 4 and numbers.isdigit()
        
    def _is_valid_eta(self, eta: str) -> bool:
        # Validate ETA format (HH:MM)
        try:
            hours, minutes = map(int, eta.split(':'))
            return 0 <= hours <= 23 and 0 <= minutes <= 59
        except (ValueError, AttributeError):
            return False

    def _format_value(self, field: DataField, value: str) -> str:
        if field in [DataField.TRACTOR_PLATES, DataField.TRAILER_PLATES]:
            return ' '.join(value).upper()
        elif field == DataField.ETA:
            return value.zfill(5)  # Ensure HH:MM format
        return value
    
    async def save_driver_data(self):
        data = {
            "name": self.data.name or "",
            "tractor_number": self.data.tractor_number or "",
            "tractor_plates": self.data.tractor_plates or "",
            "trailer_number": self.data.trailer_number or "",
            "trailer_plates": self.data.trailer_plates or "",
            "eta": self.data.eta or "",
            "email" : self.data.email or ""
        }
        try:
            logger.debug("Calling save_driver_data with data: %s", data)
            result = await self.session.call_tool("save_driver_data", {"data": data})
            logger.info("Tool response: %s", result)
        except Exception as e:
            logger.error("Error calling save_driver_data tool: %s", str(e))
            #await self.session.generate_reply("Hummm, hubo un problema al guardar tus datos. ¡Pero no te preocupes, ya los tengo anotados!")
            #await self.session.say("Hummm, hubo un problema al guardar tus datos. ¡Pero no te preocupes, ya los tengo anotados!")
            await self.session.say("Hmm, there was an issue saving your data. But don't worry, I have it noted down!")

    def set_participant(self, participant: rtc.RemoteParticipant):
        self.participant = participant

    async def hangup(self):
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(api.DeleteRoomRequest(room=job_ctx.room.name))
            
    @function_tool()
    async def end_call(self, ctx: RunContext):
        """Called when the user wants to end the call"""
        logger.info(f"ending the call for {self.participant.identity}")
        # let the agent finish speaking
        current_speech = ctx.session.current_speech
        if current_speech:
            await current_speech.wait_for_playout()
        await self.hangup()

    @function_tool()
    async def log_complaint(self, ctx: RunContext, reason: str):
        log_entry = f"[Complaint] {self.participant.identity}: {reason}"
        logger.info(log_entry)
        self.transcript_log.append(log_entry)
        return "I'm sorry to hear that. I've logged your concern."
    
    @function_tool()
    async def reschedule_call(self, ctx: RunContext, delay_seconds: str):
        log_entry = f"[Reschedule] {self.participant.identity} requested callback on {delay_seconds}"
        logger.info(log_entry)
        self.transcript_log.append(log_entry)
        try:
            requests.post(
                "http://localhost:8001/retry_call", 
                json={
                    "dial_info": self.dial_info,
                    "delay": delay_seconds
                }   
            )
            logger.info(f"Petición enviada al backend para reintentar en {delay_seconds} segundos")
        except Exception as e:
            logger.error(f"Fallo al contactar backend: {e}")
            return "Ocurrió un error al reprogramar la llamada."
        #await self.session.say(f"De acuerdo te volveré a llamar en {delay_seconds} segundos, gracias.")
        await self.session.say(f"Alright, I'll call you back in {delay_seconds} seconds, thanks.")
        await self.end_call(ctx)
        
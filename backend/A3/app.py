from flask import Flask, request, Response
from twilio.twiml.voice_response import VoiceResponse, Gather
from twilio.rest import Client
from daisy_assistant import DaisyAssistant
from dotenv import load_dotenv
import os
import json
import logging
import uuid
import asyncio
from openai import AsyncOpenAI

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
load_dotenv()

# Twilio and OpenAI clients
twilio_client = Client(os.getenv('TWILIO_ACCOUNT_SID'), os.getenv('TWILIO_AUTH_TOKEN'))
openai_client = AsyncOpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Store active sessions
sessions = {}

@app.route('/voice', methods=['POST'])
async def incoming_call():
    """Handle incoming Twilio call."""
    call_sid = request.form.get('CallSid')
    session_id = str(uuid.uuid4())[:8]
    daisy = DaisyAssistant(session_id)
    sessions[call_sid] = daisy
    
    logger.info(f"New call received: CallSid={call_sid}, SessionID={session_id}")
    
    response = VoiceResponse()
    welcome_message = await daisy.get_welcome_message()
    response.say(welcome_message, voice='Polly.Mia-Neural', language='es-MX')
    
    gather = Gather(input='speech', action='/process_input', method='POST', speech_timeout='auto')
    response.append(gather)
    
    return Response(str(response), mimetype='text/xml')

@app.route('/process_input', methods=['POST'])
async def process_input():
    """Process user speech input from Twilio."""
    call_sid = request.form.get('CallSid')
    user_input = request.form.get('SpeechResult', '').strip()
    
    if call_sid not in sessions:
        logger.error(f"No session found for CallSid={call_sid}")
        response = VoiceResponse()
        response.say("Lo siento, ocurrió un error. Por favor intenta de nuevo.", voice='Polly.Mia-Neural', language='es-MX')
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    daisy = sessions[call_sid]
    logger.info(f"Processing input for CallSid={call_sid}: {user_input}")
    
    response = VoiceResponse()
    try:
        result = await daisy.process_user_input(user_input, openai_client)
        if result['status'] == 'ended':
            response.say(result['message'], voice='Polly.Mia-Neural', language='es-MX')
            response.hangup()
            del sessions[call_sid]
        else:
            response.say(result['message'], voice='Polly.Mia-Neural', language='es-MX')
            gather = Gather(input='speech', action='/process_input', method='POST', speech_timeout='auto')
            response.append(gather)
    except Exception as e:
        logger.error(f"Error processing input: {str(e)}")
        response.say("Lo siento, ocurrió un error. Por favor intenta de nuevo.", voice='Polly.Mia-Neural', language='es-MX')
        response.hangup()
        del sessions[call_sid]
    
    return Response(str(response), mimetype='text/xml')

@app.route('/make_call', methods=['POST'])
async def make_call():
    """Inicia una llamada saliente desde el número de Twilio."""
    to_number = request.form.get('to_number')
    if not to_number:
        return {"error": "Falta el número destino"}, 400
    
    try:
        call = twilio_client.calls.create(
            to=to_number,
            from_=os.getenv('TWILIO_PHONE_NUMBER'),
            url=f"{os.getenv('NGROK_URL')}/handle_outgoing_call",
            method='POST'
        )
        logger.info(f"Llamada iniciada: CallSid={call.sid}, To={to_number}")
        return {"message": f"Llamada iniciada con CallSid={call.sid}"}, 200
    except Exception as e:
        logger.error(f"Error al iniciar llamada: {str(e)}")
        return {"error": str(e)}, 500

@app.route('/handle_outgoing_call', methods=['POST'])
async def handle_outgoing_call():
    """Maneja la llamada saliente y comienza la interacción con Daisy."""
    call_sid = request.form.get('CallSid')
    session_id = str(uuid.uuid4())[:8]
    daisy = DaisyAssistant(session_id)
    sessions[call_sid] = daisy
    
    logger.info(f"Llamada saliente recibida: CallSid={call_sid}, SessionID={session_id}")
    
    response = VoiceResponse()
    welcome_message = await daisy.get_welcome_message()
    response.say(welcome_message, voice='Polly.Mia-Neural', language='es-MX')
    
    gather = Gather(input='speech', action='/process_input', method='POST', speech_timeout='auto')
    response.append(gather)
    
    return Response(str(response), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5200)
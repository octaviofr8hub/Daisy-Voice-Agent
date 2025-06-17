'''
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
from datetime import datetime

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
    
    gather = Gather(input='speech', action='/process_input', method='POST', speech_timeout='auto', language="es")
    response.append(gather)
    
    return Response(str(response), mimetype='text/xml')

@app.route('/process_input', methods=['POST'])
async def process_input():
    """Process user speech input from Twilio."""
    call_sid = request.form.get('CallSid')
    user_input = request.form.get('SpeechResult', '').strip()
    
    logger.info(f"Processing input: CallSid={call_sid}, UserInput={user_input}")  # Log inicial

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
        start_time = datetime.now()
        result = await daisy.process_user_input(user_input, openai_client)
        end_time = datetime.now()
        logger.info(f"Process_user_input took {(end_time - start_time).total_seconds()} seconds")
        if result['status'] == 'ended':
            response.say(result['message'], voice='Polly.Mia-Neural', language='es-MX')
            response.hangup()
            del sessions[call_sid]
        else:
            response.say(result['message'], voice='Polly.Mia-Neural', language='es-MX')
            gather = Gather(input='speech', action='/process_input', method='POST', speech_timeout='auto', language="es")
            response.append(gather)
    except Exception as e:
        logger.error(f"Error processing input: {str(e)}", exc_info=True)
        response.say("Lo siento, ocurrió un error. Por favor intenta de nuevo.", voice='Polly.Mia-Neural', language='es-MX')
        response.hangup()
        del sessions[call_sid]
    logger.info(f"Returning TwiML: {str(response)}")  # Log de la respuesta TwiML
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
    
    gather = Gather(input='speech', action='/process_input', method='POST', speech_timeout='auto', language="es")
    response.append(gather)
    
    return Response(str(response), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5200)
    '''
import os
import uuid
import logging
from datetime import datetime
from flask import Flask, Response, request
from twilio.twiml.voice_response import VoiceResponse, Gather
from daisy_assistant import DaisyAssistant
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)

# Initialize OpenAI client
openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Store active sessions
sessions = {}

@app.route('/voice', methods=['POST'])
async def incoming_call():
    """Handle incoming Twilio call."""
    call_sid = request.form.get('CallSid')
    logger.info(f"Incoming call with CallSid={call_sid}")
    session_id = str(uuid.uuid4())[:8]
    daisy = DaisyAssistant(session_id)
    sessions[call_sid] = daisy
    
    logger.info(f"New call received: CallSid={call_sid}, SessionID={session_id}")
    
    response = VoiceResponse()
    welcome_message = await daisy.get_welcome_message()
    response.say(welcome_message, voice='Polly.Mia-Neural', language='es-MX')
    
    gather = Gather(input='speech', action='/process_input', method='POST',  language='es-MX')
    response.append(gather)
    
    logger.info(f"Returning TwiML: {str(response)}")
    return Response(str(response), mimetype='text/xml')

@app.route('/process_input', methods=['POST'])
async def process_input():
    """Process user speech input from Twilio."""
    call_sid = request.form.get('CallSid')
    user_input = request.form.get('SpeechResult', '').strip()
    
    logger.info(f"Processing input: CallSid={call_sid}, UserInput={user_input}")
    
    if call_sid not in sessions:
        logger.error(f"No session found for CallSid={call_sid}")
        response = VoiceResponse()
        response.say("Lo siento, ocurrió un error. Por favor intenta de nuevo.", voice='Polly.Mia-Neural', language='es-MX')
        response.hangup()
        return Response(str(response), mimetype='text/xml')
    
    daisy = sessions[call_sid]
    
    response = VoiceResponse()
    try:
        start_time = datetime.now()
        result = await daisy.process_user_input(user_input, openai_client)
        end_time = datetime.now()
        logger.info(f"Process_user_input took {(end_time - start_time).total_seconds()} seconds")
        
        logger.debug(f"Result from Daisy: {result}")
        if result['status'] == 'ended':
            response.say(result['message'], voice='Polly.Mia-Neural', language='es-MX')
            response.hangup()
            del sessions[call_sid]
        else:
            response.say(result['message'], voice='Polly.Mia-Neural', language='es-MX')
            gather = Gather(input='speech', action='/process_input', method='POST', language='es-MX')
            response.append(gather)
    except Exception as e:
        logger.error(f"Error processing input: {str(e)}", exc_info=True)
        response.say("Lo siento, ocurrió un error. Por favor intenta de nuevo.", voice='Polly.Mia-Neural', language='es-MX')
        response.hangup()
        del sessions[call_sid]
    
    logger.info(f"Returning TwiML: {str(response)}")
    return Response(str(response), mimetype='text/xml')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5200)
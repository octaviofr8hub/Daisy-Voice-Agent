import os
import json
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from agents.voice_agent import VoiceAgent
from livekit import api
from livekit.plugins import ( 
    silero, 
    openai, 
    elevenlabs,
    assemblyai, 
    deepgram,
    noise_cancellation 
) 
from livekit.agents import ( 
    AgentSession,  
    JobContext,   
    cli, 
    WorkerOptions, 
    RoomInputOptions,
    mcp 
)

logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)
load_dotenv(override=True)
outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")
print(outbound_trunk_id)
async def entrypoint(ctx: JobContext):
    logger.info(f"connecting to room {ctx.room.name}")
    await ctx.connect()
    dial_info = json.loads(ctx.job.metadata)
    logger.info(f"Data received: {dial_info}")
    participant_identity = "carrier"
    phone_number = dial_info["phone_number"]
    if not phone_number or not isinstance(phone_number, str) or not phone_number.startswith('+'):
        logger.error(f"Número de teléfono inválido: {phone_number}")
        raise ValueError("El número de teléfono debe estar en formato E.164 (por ejemplo, +1234567890)")
    # look up the user's phone number and appointment details
    voice_agent = VoiceAgent(dial_info=dial_info)
    session = AgentSession(
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        #stt=openai.STT(
        #   use_realtime=True, 
        #    language="en",
        #    model="gpt-4o-transcribe",
        #),
        llm=openai.LLM(model="gpt-4o"),
        #tts=elevenlabs.TTS(
        #    voice_id="8DzKSPdgEQPaK5vKG0Rs",  # Puedes especificar la voz que desees de ElevenLabs
        #    model="eleven_multilingual_v2"  # O el modelo que prefieras
        #),
        tts=openai.TTS(voice="onyx"),
        #tts=elevenlabs.TTS(
        #    voice_id="CaJslL1xziwefCeTNzHv",  # Puedes especificar la voz que desees de ElevenLabs
        #    model="eleven_multilingual_v2"  # O el modelo que prefieras
        #),
        mcp_servers=[
            mcp.MCPServerHTTP(url="http://localhost:8000/sse")
        ]
    )
    # Save transcript at shutdown
    '''
    async def write_transcript():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"logs/transcript_{ctx.room.name}_{timestamp}.json"
        full_transcript = {
            "transcript": session.history.to_dict(),
            "custom_log": voice_agent.transcript_log,
        }
        os.makedirs("logs", exist_ok=True)
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(full_transcript, f, indent=2)
        logger.info(f"Transcript saved to {filename}")
    ctx.add_shutdown_callback(write_transcript)
    '''
    # Start the session first before dialing
    session_started = asyncio.create_task(
        session.start(
            agent=voice_agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVCTelephony()
            ),
        )
    )
    # Dial the user
    try:
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity=participant_identity,
                wait_until_answered=True,
            )
        )
        # Wait for the agent session start and participant join
        await session_started
        participant = await ctx.wait_for_participant(identity=participant_identity)
        logger.info(f"participant joined: {participant.identity}")
        voice_agent.set_participant(participant)
    except api.TwirpError as e:
        logger.error(
            f"error creating SIP participant: {e.message}, "
            f"SIP status: {e.metadata.get('sip_status_code')} "
            f"{e.metadata.get('sip_status')}"
        )
        ctx.shutdown()
    
if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
        )
    )
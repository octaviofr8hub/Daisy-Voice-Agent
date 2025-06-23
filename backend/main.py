from __future__ import annotations
import asyncio
from livekit import rtc
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.multimodal import MultimodalAgent, AgentTranscriptionOptions
from livekit.plugins import openai, elevenlabs
from dotenv import load_dotenv
from daisy_assistant_fnc import DaisyAssistantFnc
from daisy_fsm import ConversationStateMachine
from prompts import INSTRUCTIONS
import logging
import os

# Configura el logger para main
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

load_dotenv()

# Punto de entrada principal de la aplicación
async def entrypoint(ctx: JobContext):
    logger.debug("Iniciando entrypoint")
    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
        logger.debug("Conexión establecida con LiveKit")
        await ctx.wait_for_participant()
        logger.debug("Participante conectado")
    except Exception as e:
        logger.error(f"Error en conexión o espera de participante: {str(e)}")
        return

     # Configura ElevenLabs TTS con un objeto Voice
    elevenlabs_voice = elevenlabs.tts.Voice(
        id="MPAa8GSBiMLjMLVwn0Hq",  # Tu voice_id
        name="Custom Voice",  # Nombre arbitrario
        category="premade",   # O "cloned" si es una voz personalizada
        settings=elevenlabs.tts.VoiceSettings(
            stability=0.71,
            similarity_boost=0.5,
            style=0.0,
            use_speaker_boost=True
        )
    )

    # Configura ElevenLabs TTS
    elevenlabs_tts = elevenlabs.TTS(
        voice=elevenlabs_voice,  # Cambia por tu voice_id válido
        model="eleven_multilingual_v2",
        api_key=os.getenv("ELEVEN_API_KEY"),
        encoding="mp3_44100_128",
    )

    # Configura el AudioSource para publicar audio
    audio_source = rtc.AudioSource(sample_rate=44100, num_channels=1)
    track = rtc.LocalAudioTrack.create_audio_track("agent-mic", audio_source)
    options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
    publication = await ctx.room.local_participant.publish_track(track, options)
    await publication.wait_for_subscription()
    logger.debug("Track de audio publicado")

    # Configura el modelo de OpenAI para la interacción en tiempo real
    openai_realtime_model = openai.realtime.RealtimeModel(
        model="gpt-4o-realtime-preview",
        instructions=INSTRUCTIONS,
        temperature=0.8,
        modalities=["text"],
        voice=None,
        output_audio_format=None,  # Desactiva formato de salida de audio
        input_audio_transcription=None,  # Desactiva transcripción de entrada
        turn_detection=None  # Desactiva detección de turno
    )
    

    # Inicializa el contexto de funciones del asistente
    assistant_fnc = DaisyAssistantFnc()
    logger.debug("DaisyAssistantFnc inicializado")

    # Crea el agente multimodal con el modelo y el contexto de funciones
    assistant = MultimodalAgent(
        model=openai_realtime_model, 
        fnc_ctx=assistant_fnc,
        transcription=AgentTranscriptionOptions(
            user_transcription=True,
            agent_transcription=False  # Desactiva transcripción del agente
        )
    )
    logger.debug("MultimodalAgent creado")

    # Inicia el agente en la sala
    try:
        assistant.start(ctx.room)
        logger.debug("Agente iniciado en la sala")
    except Exception as e:
        logger.error(f"Error al iniciar el agente: {str(e)}")
        return

    # Obtiene la primera sesión del modelo
    session = openai_realtime_model.sessions[0]
    
    logger.debug("Sesión obtenida")

     
    # Inicializa la máquina de estados con la sesión, logger y contexto de funciones
    #daisy_state_machine = ConversationStateMachine(session, assistant_fnc)
    # Inicializa la máquina de estados con TTS y AudioSource
    # Desactiva eventos de audio de OpenAI
    
    daisy_state_machine = ConversationStateMachine(
        session=session,
        assistant_fnc=assistant_fnc,
        tts=elevenlabs_tts,
        audio_source=audio_source
    )
    logger.debug("ConversationStateMachine inicializada")

    # Envía el mensaje de bienvenida
    try:
        await daisy_state_machine.send_welcome()
        logger.debug("Mensaje de bienvenida enviado")
    except Exception as e:
        logger.error(f"Error al enviar mensaje de bienvenida: {str(e)}")

    def on_user_speech_committed(msg: llm.ChatMessage):
        logger.debug(f"Evento user_speech_committed recibido: {msg.content}")
        try:
            if isinstance(msg.content, list):
                msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
            asyncio.create_task(daisy_state_machine.process_user_input(msg))
        except Exception as e:
            logger.error(f"Error al procesar mensaje de voz: {str(e)}")
    session.on("user_speech_committed", on_user_speech_committed)

if __name__ == "__main__":
    logger.debug("Ejecutando aplicación")
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))

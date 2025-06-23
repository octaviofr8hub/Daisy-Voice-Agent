from __future__ import annotations
import asyncio
import os
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit import rtc
from livekit.plugins import openai, elevenlabs
from dotenv import load_dotenv
from daisy_assistant_fnc import DaisyAssistantFnc
from daisy_fsm_stt import ConversationStateMachine
from prompts import INSTRUCTIONS
import logging
import openai as openai_client_asyn
import time
import wave

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

load_dotenv()

async def entrypoint(ctx: JobContext):
    logger.debug("Iniciando entrypoint")
    try:
        await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
        logger.debug("Conexión establecida con LiveKit")
        await ctx.wait_for_participant()
        logger.debug("Participante conectado")
    except Exception as e:
        logger.error(f"Error en conexión o espera de participante: {str(e)}")
        return

    # Configura ElevenLabs TTS
    elevenlabs_voice = elevenlabs.tts.Voice(
        id="CaJslL1xziwefCeTNzHv",
        name="Custom Voice",
        category="premade",
        settings=elevenlabs.tts.VoiceSettings(
            stability=0.71,
            similarity_boost=0.5,
            style=0.0,
            use_speaker_boost=True
        )
    )
    elevenlabs_tts = elevenlabs.TTS(
        voice=elevenlabs_voice,
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

    # Configura el STT
    stt = openai.STT(
        language="es",
        model="whisper-1",
        api_key=os.getenv("OPENAI_API_KEY")
    )
    logger.debug("STT configurado")

    # Inicializa el contexto de funciones
    assistant_fnc = DaisyAssistantFnc()
    logger.debug("DaisyAssistantFnc inicializado")

    # Crea un cliente OpenAI para el LLM
    openai_client = openai_client_asyn.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    logger.debug("OpenAI AsyncClient inicializado")

    # Inicializa la máquina de estados
    daisy_state_machine = ConversationStateMachine(
        stt=stt,
        openai_client=openai_client,
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

    # Captura audio entrante
    async def handle_audio_stream(track: rtc.RemoteAudioTrack, participant_identity: str):
        logger.debug(f"Procesando pista de audio para participante: {participant_identity}")
        stream = rtc.AudioStream(track)
        audio_buffer = []
        async for event in stream:
            if not hasattr(event, 'frame'):
                logger.warning(f"Evento sin frame: {type(event)}")
                continue
            frame = event.frame
            if not isinstance(frame, rtc.AudioFrame):
                logger.warning(f"Frame no es AudioFrame: {type(frame)}")
                continue
            audio_buffer.append(frame)
            if len(audio_buffer) >= 50:  # Ajustar según latencia
                daisy_state_machine.audio_buffer.extend(audio_buffer)
                audio_buffer = []
                if len(daisy_state_machine.audio_buffer) >= 100:  # Procesar audio
                    try:
                        logger.debug(f"Procesando {len(daisy_state_machine.audio_buffer)} frames para STT")
                        # Guardar audio para depuración
                        wav_data = rtc.combine_audio_frames(daisy_state_machine.audio_buffer).to_wav_bytes()
                        timestamp = time.strftime("%Y%m%d_%H%M%S")
                        with wave.open(f"debug_audio_{timestamp}.wav", "wb") as wf:
                            wf.setnchannels(1)
                            wf.setsampwidth(2)  # 16-bit
                            wf.setframerate(44100)
                            wf.writeframes(wav_data)
                        speech_event = await stt.recognize(daisy_state_machine.audio_buffer)
                        text = speech_event.alternatives[0].text
                        logger.debug(f"Transcripción cruda: {text}")
                        if text.strip():
                            msg = llm.ChatMessage(role="user", content=text)
                            logger.debug(f"Usuario dijo: {text}")
                            await daisy_state_machine.process_user_input(msg)
                        daisy_state_machine.audio_buffer.clear()
                    except Exception as e:
                        logger.error(f"Error al procesar audio: {str(e)}")
                    '''
                    try:
                        logger.debug(f"Procesando {len(daisy_state_machine.audio_buffer)} frames para STT")
                        speech_event = await stt.recognize(daisy_state_machine.audio_buffer)
                        text = speech_event.alternatives[0].text
                        if text.strip():
                            msg = llm.ChatMessage(role="user", content=text)
                            logger.debug(f"Usuario dijo: {text}")
                            await daisy_state_machine.process_user_input(msg)
                        daisy_state_machine.audio_buffer.clear()
                    except Exception as e:
                        logger.error(f"Error al procesar audio: {str(e)}")
                    '''
    # Escucha eventos de pistas
    def on_track_subscribed(publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        logger.debug(f"Pista suscrita: {publication.sid}, participante: {participant.identity}")
        if publication.track and isinstance(publication.track, rtc.RemoteAudioTrack):
            asyncio.create_task(handle_audio_stream(publication.track, participant.identity))

    def on_track_published(publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        logger.debug(f"Pista publicada: {publication.sid}, participante: {participant.identity}")

    ctx.room.on("track_subscribed", on_track_subscribed)
    ctx.room.on("track_published", on_track_published)

    # Revisa participantes existentes
    for participant in ctx.room.remote_participants.values():
        logger.debug(f"Participante inicial: {participant.identity}, publicaciones: {list(participant.track_publications.keys())}")
        for publication in participant.track_publications.values():
            if publication.track and isinstance(publication.track, rtc.RemoteAudioTrack):
                logger.debug(f"Pista inicial encontrada: {publication.sid}")
                asyncio.create_task(handle_audio_stream(publication.track, participant.identity))

if __name__ == "__main__":
    logger.debug("Ejecutando aplicación")
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
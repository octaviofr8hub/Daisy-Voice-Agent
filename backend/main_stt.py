from __future__ import annotations
import asyncio
import os
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.stt import StreamAdapter, SpeechStream
from livekit import rtc
from livekit.plugins import openai, elevenlabs, silero
from dotenv import load_dotenv
from daisy_assistant_fnc import DaisyAssistantFnc
from daisy_fsm_stt import ConversationStateMachine
from prompts import INSTRUCTIONS
import logging
import openai as openai_client_asyn
import time
from openai import OpenAIError
import wave
from pydub import AudioSegment
import io
import numpy as np

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
        detect_language=True,
        api_key=os.getenv("OPENAI_API_KEY")
    )
    logger.debug("STT configurado")

    # Configurar VAD con Silero
    vad = silero.VAD.load(
        sample_rate=16000,  # Silero solo soporta 8000 o 16000 Hz
        activation_threshold=0.5,  # Sensibilidad para detectar voz
        min_speech_duration=0.5,  # 500ms de voz mínima
        min_silence_duration=0.55,  # 550ms de silencio para separar
        prefix_padding_duration=0.5,  # 500ms de padding inicial
        max_buffered_speech=30.0,  # 30 segundos de buffer máximo
        force_cpu=True  # Por compatibilidad
    )
    logger.debug("VAD configurado")
    
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
        stt_stream = StreamAdapter(stt=stt, vad=vad)
        async for event in stream:
            if not hasattr(event, 'frame'):
                logger.warning(f"Evento sin frame: {type(event)}")
                continue
            frame = event.frame
            if not isinstance(frame, rtc.AudioFrame):
                logger.warning(f"Frame no es AudioFrame: {type(frame)}")
                continue
            # Remuestrear de 44100 Hz a 16000 Hz usando pydub
            try:
                # Convertir AudioFrame a bytes
                frame_data = np.frombuffer(frame.data, dtype=np.int16)
                audio_segment = AudioSegment(
                    data=frame_data.tobytes(),
                )
                # Remuestrear a 16000 Hz
                resampled_audio = audio_segment.set_frame_rate(16000)
                # Convertir de vuelta a bytes para crear un nuevo AudioFrame
                resampled_data = np.frombuffer(resampled_audio.raw_data, dtype=np.int16)
                resampled_frame = rtc.AudioFrame(
                    data=resampled_data.tobytes(),
                    sample_rate=16000,
                    num_channels=1,
                    samples_per_channel=len(resampled_data)
                )
                stt_stream.push_frame(resampled_frame)
            except Exception as e:
                logger.error(f"Error al remuestrear frame: {str(e)}")
                continue
            try:
                speech_event = await stt_stream.flush()
                if speech_event and hasattr(speech_event, 'text') and speech_event.text.strip():
                    text = speech_event.text
                    logger.debug(f"Transcripción cruda: {text}")
                    msg = llm.ChatMessage(role="user", content=text)
                    logger.debug(f"Usuario dijo: {text}")
                    await daisy_state_machine.process_user_input(msg)
            except OpenAIError as e:
                logger.error(f"Error de OpenAI en STT: {str(e)}")
            except Exception as e:
                logger.error(f"Error inesperado en STT: {str(e)}")
        await stt_stream.aclose()
        logger.debug("STT stream cerrado")

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
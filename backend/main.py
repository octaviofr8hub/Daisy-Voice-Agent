from __future__ import annotations
import asyncio
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
from dotenv import load_dotenv
from daisy_assistant_fnc import DaisyAssistantFnc

from daisy_fsm import ConversationStateMachine
#from logger import ConversationLogger
from daisy_prompts import INSTRUCTIONS

import logging


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

    # Configura el modelo de OpenAI para la interacción en tiempo real
    openai_realtime_model = openai.realtime.RealtimeModel(
        model="gpt-4o-realtime-preview",
        instructions=INSTRUCTIONS,
        voice="shimmer",
        temperature=0.8,
        modalities=["audio", "text"],
    )
    

    # Inicializa el contexto de funciones del asistente
    assistant_fnc = DaisyAssistantFnc()
    logger.debug("DaisyAssistantFnc inicializado")

    # Crea el agente multimodal con el modelo y el contexto de funciones
    assistant = MultimodalAgent(model=openai_realtime_model, fnc_ctx=assistant_fnc)
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
    daisy_state_machine = ConversationStateMachine(session, assistant_fnc)
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

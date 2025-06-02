from __future__ import annotations
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
from dotenv import load_dotenv
from api import AssistantFnc
from state_machine import ConversationStateMachine
from logger import ConversationLogger
from daisy_prompts import INSTRUCTIONS

load_dotenv()

# Punto de entrada principal de la aplicación
async def entrypoint(ctx: JobContext):
    # Conecta al contexto con suscripción automática a todos los eventos
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    # Espera a que un participante se conecte
    await ctx.wait_for_participant()
    
    # Configura el modelo de OpenAI para la interacción en tiempo real
    openai_realtime_model = openai.realtime.RealtimeModel(  
        model="gpt-4o-realtime-preview",
        instructions=INSTRUCTIONS,
        voice="shimmer",
        temperature=0.8,
        modalities=["audio", "text"]
    )
    # Inicializa el contexto de funciones del asistente
    assistant_fnc = AssistantFnc()
    # Crea el agente multimodal con el modelo y el contexto de funciones
    #assistant = MultimodalAgent(model=model, fnc_ctx=assistant_fnc)
    assistant = MultimodalAgent(model=openai_realtime_model)
    
    # Workaround para evitar errores de playout
    def _on_playout_started(*args, **kwargs):
        pass
    def _on_playout_stopped(*args, **kwargs):
        pass
    assistant._on_playout_started = _on_playout_started
    assistant._on_playout_stopped = _on_playout_stopped
    
    # Inicia el agente en la sala
    assistant.start(ctx.room)
    
    # Obtiene la primera sesión del modelo
    session = openai_realtime_model.sessions[0]
    
    # Inicializa el logger para registrar la conversación
    logger = ConversationLogger()
    # Inicializa la máquina de estados con la sesión y el logger
    state_machine = ConversationStateMachine(session, logger)
    
    # Envía el mensaje de bienvenida
    await state_machine.send_welcome()
    
    # Maneja mensajes de voz del usuario
    @session.on("user_speech_committed")
    async def on_user_speech_committed(msg: llm.ChatMessage):
        await state_machine.process_user_input(msg)

    # Maneja mensajes de texto del usuario
    @assistant.on("text_stream")
    async def on_text_stream(msg: llm.ChatMessage):
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
        await state_machine.process_user_input(msg)

# Ejecuta la aplicación con el entrypoint definido
if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
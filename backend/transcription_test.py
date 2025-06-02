from __future__ import annotations
from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.multimodal import MultimodalAgent
from livekit.plugins import openai
from dotenv import load_dotenv
import re

load_dotenv()

def clean_user_text(raw: str, field: str) -> str:
    raw = raw.strip()
    if field == "nombre_operador":
        m = re.search(r"(?:mi nombre es|me llamo|soy|el nombre es)\s+(.+)", raw, re.IGNORECASE)
        name = m.group(1).strip() if m else raw
        return " ".join(p.capitalize() for p in name.split())
    elif field in ("numero_tractor", "numero_trailer"):
        digits = re.findall(r"\d", raw)
        return "".join(digits) if digits else raw
    elif field in ("placas_tractor", "placas_trailer"):
        plate = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
        return plate
    return raw

async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.SUBSCRIBE_ALL)
    await ctx.wait_for_participant()

    model = openai.realtime.RealtimeModel(
        model="gpt-4o-realtime-preview",
        instructions="Solo transcribe lo que se dice. No respondas. No hagas ninguna acción.",
        voice=None,
        temperature=0.8,
        modalities=["audio"]
    )

    #assistant = MultimodalAgent(model=model)  # fnc_ctx eliminado

    # Desactivar respuesta en audio
    #assistant._on_playout_started = lambda *args, **kwargs: None
    #assistant._on_playout_stopped = lambda *args, **kwargs: None

    #assistant.start(ctx.room)

    session = model.sessions[0]

    @session.on("user_speech_committed")
    async def on_user_speech_committed(msg: llm.ChatMessage):
        if isinstance(msg.content, list):
            msg.content = "\n".join("[image]" if isinstance(x, llm.ChatImage) else x for x in msg.content)
        user_text = msg.content.strip()
        print(f"[TRANSCRIPCIÓN] {user_text}")

    #@assistant.on("text_stream")
    #async def on_text_stream(msg: llm.ChatMessage):
    #    await on_user_speech_committed(msg)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))


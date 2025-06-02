import re
import os
import json
from datetime import datetime
import config

# Verifica si el texto del usuario contiene una solicitud de repetición
def is_repeat_request(text: str) -> bool:
    text = text.lower()
    return any(trigger in text for trigger in config.REPEAT_REQUESTS)

# Verifica si el texto del usuario está fuera de tema
def is_off_topic(text: str) -> bool:
    text = text.lower()
    return any(trigger in text for trigger in config.OFF_TOPIC_TRIGGERS)

# Limpia y formatea el texto del usuario según el campo que se está recolectando
def clean_user_text(raw: str, field: str) -> str:
    raw = raw.strip()
    if field == "nombre_operador":
        # Extrae el nombre después de frases como "mi nombre es" y lo formatea
        m = re.search(r"(?:mi nombre es|me llamo|soy|el nombre es)\s+(.+)", raw, re.IGNORECASE)
        name = m.group(1).strip() if m else raw
        return " ".join(p.capitalize() for p in name.split())
    elif field in ("numero_tractor", "numero_trailer"):
        # Extrae solo dígitos para números de tractor o tráiler
        digits = re.findall(r"\d", raw)
        if digits:
            return "".join(digits)
        return raw
    elif field in ("placas_tractor", "placas_trailer"):
        # Extrae caracteres alfanuméricos y los convierte a mayúsculas para placas
        plate = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
        return plate
    return raw

# Guarda la conversación en un archivo JSON
def save_conversation_to_json(conversation_log, session_id: str):
    try:
        output_dir = "conversation_logs"
        # Crea el directorio si no existe
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{output_dir}/conversation_{session_id}_{timestamp}.json"
        # Escribe el log en un archivo JSON
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(conversation_log, f, ensure_ascii=False, indent=2)
        print(f"Conversación guardada en {filename}")
    except Exception as e:
        # Registra cualquier error al intentar guardar el archivo
        print(f"Error al guardar el JSON: {str(e)}")
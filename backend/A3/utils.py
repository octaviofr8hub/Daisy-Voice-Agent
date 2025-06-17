import re
import logging
import asyncio

logger = logging.getLogger(__name__)

def clean_user_text(raw: str, field: str) -> str:
    """Clean user input text."""
    raw = raw.strip().lower()
    if field in ("nombre_operador", "numero_tractor", "numero_trailer"):
        return raw.title() if field == "nombre_operador" else raw
    return raw

def is_repeat_request(text: str) -> bool:
    """Check if user is asking to repeat."""
    repeat_phrases = {"repite", "repíteme", "otra vez", "de nuevo"}
    return any(phrase in text.lower() for phrase in repeat_phrases)

def is_off_topic(text: str) -> bool:
    """Check if user input is off-topic."""
    off_topic_phrases = {"no sé", "qué", "hola", "adiós", "gracias"}
    return any(phrase in text.lower() for phrase in off_topic_phrases) and not is_repeat_request(text)

async def infer_plate_from_text(raw: str, openai_client) -> str:
    """Detecta la placa vehicular usando OpenAI."""
    prompt = """
    Detecta y devuelve únicamente la placa vehicular mencionada por el usuario en formato LETRAS-NÚMEROS (e.g., ABC-1234, XY-1234).
    - Ignora muletillas como "esteee", "umm", "creo".
    - Convierte números en texto (e.g., "cuatro cinco seis" → "456").
    - Normaliza el formato (e.g., "A B C guión 1 2 3 4" → "ABC-1234").
    - Si no hay placa clara, devuelve una cadena vacía.

    Ejemplos:
    - Entrada: "Las placas son ABC-1234" → Salida: ABC-1234
    - Entrada: "Esteee, es A B C guión uno dos tres cuatro" → Salida: ABC-1234
    - Entrada: "Placas D-E-F cuatro cinco seis siete" → Salida: DEF-4567
    - Entrada: "Creo que es zac cuatro cinco seis uno" → Salida: ZAC-4561
    - Entrada: "No sé, algo así como tango bravo 123" → Salida: TB-123
    - Entrada: "Hola, cómo estás" → Salida: ""

    Entrada: "{raw}"
    Salida:
    """.format(raw=raw)

    try:
        task = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        response = await asyncio.wait_for(task, timeout=5.0)
        plate = response.choices[0].message.content.strip().upper()
        if re.match(r"^[A-Z]{2,3}-[0-9]{3,4}$", plate):
            return plate
        return ""
    except asyncio.TimeoutError:
        logger.error(f"Timeout inferring plate for input: {raw}")
        return ""
    except Exception as e:
        logger.error(f"Error inferring plate: {str(e)}")
        return ""

async def infer_eta_from_text(raw: str, openai_client) -> str:
    """Detecta el ETA en formato HH:MM usando OpenAI."""
    prompt = """
    Detecta y devuelve únicamente el ETA mencionado por el usuario en formato HH:MM (e.g., 14:30, 09:15).
    - Ignora muletillas como "esteee", "umm", "creo".
    - Convierte números en texto (e.g., "catorce treinta" → "14:30").
    - Normaliza el formato (e.g., "catorce y treinta" → "14:30").
    - Si no hay un ETA claro o válido, devuelve una cadena vacía.

    Ejemplos:
    - Entrada: "Mi ETA es a las 14:30" → Salida: 14:30
    - Entrada: "Esteee, catorce treinta" → Salida: 14:30
    - Entrada: "Ummm, la ETA sería como a las dieciséis cero cero" → Salida: 16:00
    - Entrada: "Llegada a las veinte cero cero" → Salida: 20:00
    - Entrada: "No sé, mañana por la mañana" → Salida: ""
    - Entrada: "A las tres quince de la tarde" → Salida: 15:15

    Entrada: "{raw}"
    Salida:
    """.format(raw=raw)

    try:
        task = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        response = await asyncio.wait_for(task, timeout=5.0)
        eta = response.choices[0].message.content.strip()
        if re.match(r"^[0-2][0-9]:[0-5][0-9]$", eta) and 0 <= int(eta.split(":")[0]) <= 23:
            return eta
        return ""
    except asyncio.TimeoutError:
        logger.error(f"Timeout inferring ETA for input: {raw}")
        return ""
    except Exception as e:
        logger.error(f"Error inferring ETA: {str(e)}")
        return ""
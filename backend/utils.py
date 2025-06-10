import re
import config
from unidecode import unidecode
from number_parser import parse_number
from asi1_agent import ASI1RequestWrapper
from dotenv import load_dotenv
import os

load_dotenv()

NUMBER_WORDS = {
    'cero': '0', 'uno': '1', 'dos': '2', 'tres': '3', 'cuatro': '4',
    'cinco': '5', 'seis': '6', 'siete': '7', 'ocho': '8', 'nueve': '9',
    'diez': '10', 'once': '11', 'doce': '12', 'trece': '13', 'catorce': '14',
    'quince': '15', 'dieciseis': '16', 'diecisiete': '17', 'dieciocho': '18', 'diecinueve': '19',
    'veinte': '20'
}


# Diccionario para convertir números en texto a dígitos
SPANISH_DIGITS = {
    "cero": "0", "uno": "1", "dos": "2", "tres": "3", "cuatro": "4",
    "cinco": "5", "seis": "6", "siete": "7", "ocho": "8", "nueve": "9",
    "diez": "10", "once": "11", "doce": "12", "trece": "13", "catorce": "14",
    "quince": "15", "dieciséis": "16", "diecisiete": "17", "dieciocho": "18",
    "diecinueve": "19", "veinte": "20", "veintiuno": "21", "veintidós": "22",
    "veintitrés": "23"
}

# Muletillas comunes en español mexicano
MULETILLAS = [
    r"\b(esteee)\b", r"\b(umm+)\b", r"\b(creo)\b", r"\b(ehh+)\b", r"\b(a ver)\b",
    r"\b(bueno)\b", r"\b(este)\b", r"\b(ósea)\b", r"\b(vale)\b"
]

def words_to_digits(text: str) -> str:
    """Convierte números escritos en palabras a dígitos."""
    text = unidecode(text.lower())
    for word, digit in NUMBER_WORDS.items():
        text = text.replace(word, digit)
    return text

# Verifica si el texto del usuario contiene una solicitud de repetición
def is_repeat_request(text: str) -> bool:
    text = text.lower()
    return any(trigger in text for trigger in config.REPEAT_REQUESTS)

# Verifica si el texto del usuario está fuera de tema
def is_off_topic(text: str) -> bool:
    text = text.lower()
    return any(trigger in text for trigger in config.OFF_TOPIC_TRIGGERS)

def clean_user_text(raw: str, current_field: str) -> str:
    """
    Limpia el texto del usuario según el campo actual.
    """
    raw = raw.strip().lower()
    
    # Eliminar muletillas
    for muletilla in MULETILLAS:
        raw = re.sub(muletilla, "", raw, flags=re.IGNORECASE)
    
    # Normalizar espacios
    raw = re.sub(r"\s+", " ", raw).strip()
    
    if current_field == "nombre_operador":
        m = re.search(r"(?:mi nombre es|me llamo|soy|el nombre del operador es|el nombre es)\s+(.+)", raw, re.IGNORECASE)
        name = m.group(1).strip() if m else raw
        return " ".join(p.capitalize() for p in name.split())
    
    elif current_field in ("numero_tractor", "numero_trailer"):
        # Extraer dígitos directamente
        digits = re.findall(r"\d", raw)
        if digits:
            return "".join(digits)
        # Convertir números en texto
        try:
            num = parse_number(raw, language="es")
            if num is not None:
                return str(num)
        except Exception:
            pass
        # Mapear palabras a dígitos
        tokens = raw.split()
        mapped = [SPANISH_DIGITS.get(tok) for tok in tokens if tok in SPANISH_DIGITS]
        if mapped:
            return "".join(mapped)
        return raw
    
    elif current_field in ("placas_tractor", "placas_trailer"):
        # Preprocesar para placas
        # Reemplazar "guión" por "-"
        raw = re.sub(r"\bguion\b|\bguion\b", "-", raw, flags=re.IGNORECASE)
        # Eliminar "las placas son" o similares
        raw = re.sub(r"\b(las placas son|placas|son)\b", "", raw, flags=re.IGNORECASE)
        # Convertir números en texto a dígitos
        tokens = raw.split()
        converted = []
        for token in tokens:
            if token in SPANISH_DIGITS:
                converted.append(SPANISH_DIGITS[token])
            else:
                converted.append(token)
        raw = " ".join(converted)
        # Normalizar formato (e.g., "A B C - 1 2 3 4" -> "ABC-1234")
        raw = re.sub(r"\s*-\s*", "-", raw)
        raw = re.sub(r"\s+", "", raw)
        return raw.upper()
    
    elif current_field == "eta":
        # Preprocesar ETA
        raw = re.sub(r"\b(a las|alrededor de|como a las|horas|de la tarde|de la mañana|son las|)\b", "", raw, flags=re.IGNORECASE)
        tokens = raw.split()
        converted = []
        for token in tokens:
            if token in SPANISH_DIGITS:
                converted.append(SPANISH_DIGITS[token])
            elif token in {"y", "con"}:  # Para "catorce y treinta"
                converted.append(":")
            else:
                converted.append(token)
        raw = " ".join(converted)
        raw = re.sub(r"\s*:\s*", ":", raw)
        return raw

    return raw

async def infer_plate_from_text(raw: str) -> str:
    """
    Detecta la placa vehicular usando el modelo de OpenAI Realtime.
    """
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

    response = ASI1RequestWrapper(
        api_key=os.getenv('ASI1_API_KEY'), 
        temperature=0.3
    ).generate(prompt)
    
    if response is None:
        return ""

    # Validar formato de la placa
    plate = response.strip().upper()
    if re.match(r"^[A-Z]{2,3}-[0-9]{3,4}$", plate):
        return plate
    return ""

async def infer_eta_from_text(raw: str) -> str:
    """
    Detecta y devuelve el ETA en formato HH:MM usando el modelo de OpenAI Realtime.
    """
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

    response = ASI1RequestWrapper(
        api_key=os.getenv('ASI1_API_KEY'), 
        temperature=0.3
    ).generate(prompt)

    if response is None:
        return "No quedo claro"
    eta = response.strip()
    if re.match(r"^[0-2][0-9]:[0-5][0-9]$", eta) and 0 <= int(eta.split(":")[0]) <= 23:
        return eta
    return ""

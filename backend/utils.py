import re
import os
import json
from datetime import datetime
import config

from unidecode import unidecode

SPANISH_DIGITS = {
    "cero": "0", "uno": "1", "dos": "2", "tres": "3", "cuatro": "4",
    "cinco": "5", "seis": "6", "siete": "7", "ocho": "8", "nueve": "9",
    "diez": "10", "once": "11", "doce": "12", "trece": "13", "catorce": "14",
    "quince": "15", "dieciséis": "16", "diecisiete": "17", "dieciocho": "18",
    "diecinueve": "19", "veinte": "20", "veintiuno": "21", "veintidós": "22",
    "veintitrés": "23"
}

NUMBER_WORDS = {
    'cero': '0', 'uno': '1', 'dos': '2', 'tres': '3', 'cuatro': '4',
    'cinco': '5', 'seis': '6', 'siete': '7', 'ocho': '8', 'nueve': '9',
    'diez': '10', 'once': '11', 'doce': '12', 'trece': '13', 'catorce': '14',
    'quince': '15', 'dieciseis': '16', 'diecisiete': '17', 'dieciocho': '18', 'diecinueve': '19',
    'veinte': '20'
}

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

def clean_user_text(raw: str, field: str) -> str:
    raw = unidecode(raw.strip().lower())
    raw = words_to_digits(raw)  # Convertir palabras numéricas a dígitos

    if field == "nombre_operador":
        m = re.search(r"(?:mi nombre es|me llamo|soy|el nombre es)\s+(.+)", raw, re.IGNORECASE)
        name = m.group(1).strip() if m else raw
        return " ".join(p.capitalize() for p in name.split())
    
    elif field in ("numero_tractor", "numero_trailer"):
        # Extraer números, permitir guiones o espacios (ej. "123-456" o "123 456")
        digits = re.findall(r"\d+", raw)
        if digits:
            return "".join(digits)  # Unir todos los dígitos
        return raw
    
    elif field in ("placas_tractor", "placas_trailer"):
        # Formato típico de placas mexicanas: 3 letras + 3-4 dígitos (ABC1234) o 2 letras + 3 dígitos + 2 letras (AB123CD)
        plate = re.sub(r"[^A-Za-z0-9]", "", raw).upper()
        # Validar formato de placa
        if re.match(r"^[A-Z]{2,3}\d{3,4}$|^[A-Z]{2}\d{3}[A-Z]{2}$", plate):
            return plate
        # Si no coincide, intentar extraer solo la parte alfanumérica relevante
        match = re.search(r"[A-Z0-9]{5,7}", plate)
        return match.group(0) if match else plate
    
    elif field == "eta":
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

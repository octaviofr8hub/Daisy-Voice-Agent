# Definición de los campos que se recolectarán durante la conversación
FIELDS = [
    ("nombre_operador", "nombre completo"),
    ("numero_tractor", "número de tractor"),
    ("placas_tractor", "placas de tractor"),
    ("numero_trailer", "número de tráiler"),
    ("placas_trailer", "placas de tráiler"),
    ("eta", "ETA")
]

# Lista con los nombres de los campos en orden
FIELD_ORDER = [k for k, _ in FIELDS]

# Número total de campos a recolectar
NUM_FIELDS = len(FIELDS)

# Palabras clave que indican una solicitud de repetición por parte del usuario
REPEAT_REQUESTS = {
    "no entendí", "repíteme", "puedes repetir", "qué dijiste",
    "como dijiste", "no escuché", "de nuevo", "repite", "otra vez", "repiteme los datos",
    "vuelve a decirme los datos", "dime los datos por favor", "como como", "otra vez repitelo",
    "cuales eran mis datos"
}

# Palabras clave que indican que el usuario está fuera de tema
OFF_TOPIC_TRIGGERS = {
    "cómo estás", "qué haces", "quién eres", "qué es esto", "para qué llamas", "me puedes ayudar",
    "que es esto", "quien te hizo esto", "para que llamas"
}

# Palabras clave para activar el inicio de la conversación
#WAKE_WORDS = {"hola", "bueno", "quién es", "quien es", "daisy"}

WAKE_WORDS = {"hola", "bueno", "quién es", "quien es", "daisy", "que no", "qué no", "si"}
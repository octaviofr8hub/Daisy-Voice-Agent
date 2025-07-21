# Definición de los campos que se recolectarán durante la conversación
FIELDS = [
    ("nombre_operador", "nombre completo"),
    ("numero_tractor", "número de tractor"),
    ("placas_tractor", "placas de tractor"),
    ("numero_trailer", "número de tráiler"),
    ("placas_trailer", "placas de tráiler"),
    ("eta", "ETA"),
    ("email", "correo electronico")
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

LETTER_MAP = {
    "a": ("A", "Águila"), "á": ("A", "Águila"), "ah": ("A", "Águila"),
    "be": ("B", "Burro"), "ve": ("B", "Burro"), "uve": ("B", "Burro"), "b": ("B", "Burro"), "beta": ("B", "Burro"),
    "ce": ("C", "Casa"), "c": ("C", "Casa"),
    "de": ("D", "Dedo"), "d": ("D", "Dedo"),
    "e": ("E", "Elefante"), "é": ("E", "Elefante"),
    "efe": ("F", "Francia"), "f": ("F", "Francia"),
    "ge": ("G", "Globo"), "g": ("G", "Globo"),
    "hache": ("H", "Huevo"), "h": ("H", "Huevo"),
    "i": ("I", "Iguana"), "í": ("I", "Iguana"),
    "jota": ("J", "Jirafa"), "j": ("J", "Jirafa"),
    "ka": ("K", "Koala"), "k": ("K", "Koala"),
    "ele": ("L", "Luna"), "l": ("L", "Luna"),
    "eme": ("M", "Manzana"), "m": ("M", "Manzana"),
    "ene": ("N", "Nube"), "n": ("N", "Nube"),
    "o": ("O", "Oso"), "ó": ("O", "Oso"),
    "pe": ("P", "Perro"), "p": ("P", "Perro"),
    "cu": ("Q", "Queso"), "q": ("Q", "Queso"),
    "erre": ("R", "Rana"), "r": ("R", "Rana"),
    "ese": ("S", "Sol"), "s": ("S", "Sol"),
    "te": ("T", "Tigre"), "t": ("T", "Tigre"),
    "u": ("U", "Uva"), "ú": ("U", "Uva"),
    "uve": ("V", "Vaca"), "v": ("V", "Vaca"),
    "doble u": ("W", "Wapiti"), "w": ("W", "Wapiti"),
    "equis": ("X", "Xilófono"), "x": ("X", "Xilófono"),
    "ye": ("Y", "Yegua"), "igriega": ("Y", "Yegua"), "y": ("Y", "Yegua"),
    "zeta": ("Z", "Zanahoria"), "z": ("Z", "Zanahoria"),
    "arroba": ("@", "Arroba"),
    "punto": (".", "Punto"),
    "com": ("com", "Com"),
    "mx": ("mx", "Mx"),
    "org": ("org", "Org"),
    "net": ("net", "Net")
}

LETTER_MAP_EN = {
    "a": ("A", "Apple"), "ay": ("A", "Apple"),
    "b": ("B", "Ball"), "bee": ("B", "Ball"),
    "c": ("C", "Cat"), "see": ("C", "Cat"),
    "d": ("D", "Dog"), "dee": ("D", "Dog"),
    "e": ("E", "Elephant"), "ee": ("E", "Elephant"),
    "f": ("F", "Fish"), "eff": ("F", "Fish"),
    "g": ("G", "Goat"), "gee": ("G", "Goat"),
    "h": ("H", "Hat"), "aitch": ("H", "Hat"),
    "i": ("I", "Ice"), "eye": ("I", "Ice"),
    "j": ("J", "Jet"), "jay": ("J", "Jet"),
    "k": ("K", "Kite"), "kay": ("K", "Kite"),
    "l": ("L", "Lion"), "ell": ("L", "Lion"),
    "m": ("M", "Moon"), "em": ("M", "Moon"),
    "n": ("N", "Nest"), "en": ("N", "Nest"),
    "o": ("O", "Orange"), "oh": ("O", "Orange"),
    "p": ("P", "Pig"), "pee": ("P", "Pig"),
    "q": ("Q", "Queen"), "cue": ("Q", "Queen"),
    "r": ("R", "Rabbit"), "ar": ("R", "Rabbit"),
    "s": ("S", "Sun"), "ess": ("S", "Sun"),
    "t": ("T", "Tiger"), "tee": ("T", "Tiger"),
    "u": ("U", "Umbrella"), "you": ("U", "Umbrella"),
    "v": ("V", "Violin"), "vee": ("V", "Violin"),
    "w": ("W", "Water"), "double u": ("W", "Water"),
    "x": ("X", "X-ray"), "ex": ("X", "X-ray"),
    "y": ("Y", "Yellow"), "why": ("Y", "Yellow"),
    "z": ("Z", "Zebra"), "zee": ("Z", "Zebra"),
    "at": ("@", "At"),
    "dot": (".", "Dot"),
    "com": ("com", "Com"),
    "mx": ("mx", "Mx"),
    "org": ("org", "Org"),
    "net": ("net", "Net")
}
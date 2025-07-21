from enum import Enum
from dataclasses import dataclass

class DataField(Enum):
    NAME = "nombre completo"
    TRACTOR_NUMBER = "número de tractor"
    TRACTOR_PLATES = "placas de tractor"
    TRAILER_NUMBER = "número de tráiler"
    TRAILER_PLATES = "placas de tráiler"
    ETA = "ETA"
    EMAIL = "correo"

@dataclass
class DriverData:
    name: str = None
    tractor_number: str = None
    tractor_plates: str = None
    trailer_number: str = None
    trailer_plates: str = None
    eta: str = None
    email: str = None
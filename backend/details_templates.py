import enum

class DriverDetails(enum.Enum):
    NOMBRE_OPERADOR = "nombre_operador"
    
class TractorDetails(enum.Enum):
    NUMERO_TRACTOR = "numero_tractor"
    PLACAS_TRACTOR = "placa_tractor"

class TrailerDetails(enum.Enum):
    NUMERO_TRAILER = "numero_trailer"
    PLACA_TRAILER = "placa_trailer"

class ETADetails(enum.Enum):
    ETA = "eta"
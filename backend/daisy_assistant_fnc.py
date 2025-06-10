from livekit.agents import llm
from typing import Annotated
from details_templates import DriverDetails, TractorDetails, TrailerDetails, ETADetails
import uuid
from datetime import datetime
import json
import os

class DaisyAssistantFnc(llm.FunctionContext):
    def __init__(self):
        super().__init__()

        self._driver_details = {
            DriverDetails.NOMBRE_OPERADOR: "",
        }
        self._tractor_details = {
            TractorDetails.NUMERO_TRACTOR: "",
            TractorDetails.PLACAS_TRACTOR: ""
        }
        self._trailer_details = {
            TrailerDetails.NUMERO_TRAILER: "",
            TrailerDetails.PLACA_TRAILER: ""
        }
        self._eta_details = {
            ETADetails.ETA: ""
        }
        # Historial de mensajes para el JSON
        self._conversation_log = []
        # ID único para la sesión
        self._session_id = str(uuid.uuid4())[:8]

    def _log_message(self, role: str, content: str):
        """Registra un mensaje en el historial de la conversación."""
        self._conversation_log.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": str(content)
        })

    def _save_to_json(self):
        """Guarda los datos recolectados y el historial en un archivo JSON."""
        try:
            output_dir = "conversation_logs"
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{output_dir}/conversation_{self._session_id}_{timestamp}.json"
            data = {
                "session_id": self._session_id,
                "driver_details": {k.value: v for k, v in self._driver_details.items()},
                "tractor_details": {k.value: v for k, v in self._tractor_details.items()},
                "trailer_details": {k.value: v for k, v in self._trailer_details.items()},
                "eta_details": {k.value: v for k, v in self._eta_details.items()},
                "conversation_log": self._conversation_log
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error al guardar el JSON: {str(e)}")

    @llm.ai_callable(description="Registra el nombre del operador")
    def set_driver_name(self, nombre: Annotated[str, llm.TypeInfo(description="Nombre completo del operador")]):
        """Registra el nombre del operador y lo guarda en el estado."""
        self._driver_details[DriverDetails.NOMBRE_OPERADOR] = nombre.strip().title()
        self._log_message("system", f"Nombre del operador registrado: {nombre}")
        return f"Nombre registrado: {nombre}"

    @llm.ai_callable(description="Registra el número del tractor")
    def set_tractor_number(self, numero: Annotated[str, llm.TypeInfo(description="Número del tractor")]):
        """Registra el número del tractor y lo guarda en el estado."""
        self._tractor_details[TractorDetails.NUMERO_TRACTOR] = numero.strip()
        self._log_message("system", f"Número de tractor registrado: {numero}")
        return f"Número de tractor registrado: {numero}"

    @llm.ai_callable(description="Registra las placas del tractor")
    def set_tractor_plates(self, placas: Annotated[str, llm.TypeInfo(description="Placas del tractor")]):
        """Registra las placas del tractor y lo guarda en el estado."""
        self._tractor_details[TractorDetails.PLACAS_TRACTOR] = placas.strip().upper()
        self._log_message("system", f"Placas de tractor registradas: {placas}")
        return f"Placas de tractor registradas: {placas}"

    @llm.ai_callable(description="Registra el número del tráiler")
    def set_trailer_number(self, numero: Annotated[str, llm.TypeInfo(description="Número del tráiler")]):
        """Registra el número del tráiler y lo guarda en el estado."""
        self._trailer_details[TrailerDetails.NUMERO_TRAILER] = numero.strip()
        self._log_message("system", f"Número de tráiler registrado: {numero}")
        return f"Número de tráiler registrado: {numero}"

    @llm.ai_callable(description="Registra las placas del tráiler")
    def set_trailer_plates(self, placas: Annotated[str, llm.TypeInfo(description="Placas del tráiler")]):
        """Registra las placas del tráiler y lo guarda en el estado."""
        self._trailer_details[TrailerDetails.PLACA_TRAILER] = placas.strip().upper()
        self._log_message("system", f"Placas de tráiler registradas: {placas}")
        return f"Placas de tráiler registradas: {placas}"

    @llm.ai_callable(description="Registra el ETA en formato HH:MM")
    def set_eta(self, eta: Annotated[str, llm.TypeInfo(description="ETA en formato HH:MM")]):
        """Registra el ETA y lo guarda en el estado."""
        self._eta_details[ETADetails.ETA] = eta.strip()
        self._log_message("system", f"ETA registrado: {eta}")
        return f"ETA registrado: {eta}"

    @llm.ai_callable(description="Guarda todos los datos recolectados en un archivo JSON (Vuelve a decirle al usuario los datos que guardaste y confirmale que los guardaste)")
    def save_driver_data(self):
        """Guarda todos los datos recolectados en un archivo JSON."""
        self._log_message("system", "Guardando datos en JSON")
        self._save_to_json()
        return "Datos guardados en JSON"
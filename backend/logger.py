import uuid
from datetime import datetime
from utils import save_conversation_to_json

# Clase para gestionar el registro de la conversación
class ConversationLogger:
    def __init__(self):
        # Genera un ID único para la sesión
        self.session_id = str(uuid.uuid4())
        # Inicializa la lista para almacenar los mensajes
        self.conversation_log = []

    # Agrega un mensaje al log de la conversación
    def log_message(self, role: str, content: str, state: str, field: str = None):
        self.conversation_log.append({
            "timestamp": datetime.now().isoformat(),
            "role": role,
            "content": content,
            "state": state,
            "field": field
        })

    # Guarda el log en un archivo JSON
    def save(self):
        save_conversation_to_json(self.conversation_log, self.session_id)
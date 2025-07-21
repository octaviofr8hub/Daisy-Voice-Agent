import requests

# Inicializa el LLM con restricciones para longitud y coherencia
class ASI1RequestWrapper:
    def __init__(
            self, 
            api_key, 
            temperature=0.3
        ):
        self.api_key = api_key
        self.temperature = temperature
        self.url = "https://api.asi1.ai/v1/chat/completions"

    def generate(self, messages):
        user_prompt = messages
        payload = {
            "model": "asi1-fast",
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": self.temperature,
            "stream": False,  # Cambiado a False para evitar streaming
            "max_tokens": 500  # Límite razonable de tokens
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        try:
            response = requests.post(
                self.url, 
                headers=headers, 
                json=payload
            )
            response.raise_for_status()  # Verifica errores HTTP
            data = response.json()
            print(data["choices"][0]["message"]["content"].strip())
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print(f"Error en la solicitud a ASI1: {e}")
            return None
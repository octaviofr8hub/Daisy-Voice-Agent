import requests
import json
import os

class LLaMARequestWrapper:
    def __init__(self, api_key, temperature=0.3):
        self.api_key = api_key
        self.temperature = temperature
        self.url = "https://api-inference.huggingface.co/models/meta-llama/Llama-3.1-8B-Instruct"

    def generate(self, prompt: str) -> str:
        """Genera una respuesta usando la API de Hugging Face para LLaMA 3.1."""
        payload = {
            "inputs": prompt,
            "parameters": {
                "temperature": self.temperature,
                "max_new_tokens": 512,
                "return_full_text": False
            }
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(self.url, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            if isinstance(result, list) and result:
                return result[0].get("generated_text", "").strip()
            return ""
        except Exception as e:
            print(f"Error en la solicitud a LLaMA: {e}")
            return None

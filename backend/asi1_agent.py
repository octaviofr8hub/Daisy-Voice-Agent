import requests
import json

# Inicializa el LLM con restricciones para longitud y coherencia
class ASI1RequestWrapper:
    def __init__(self, api_key, temperature=0.3):
        self.api_key = api_key
        self.temperature = temperature
        self.url = "https://api.asi1.ai/v1/chat/completions"

    def generate(self, messages):
        user_prompt = "\n".join([msg.content for msg in messages[0]])
        payload = {
            "model": "asi1-fast",
            "messages": [{"role": "user", "content": user_prompt}],
            "temperature": self.temperature,
            "stream": True,
            "max_tokens": 0
        }
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'Authorization': f'Bearer {self.api_key}'
        }
        try:
            response = requests.post(self.url, headers=headers, json=payload, stream=True)
            output = ""
            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data:"):
                        data = decoded_line[5:].strip()
                        if data == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data)
                            delta = parsed["choices"][0]["delta"].get("content")
                            if delta:
                                output += delta
                        except Exception as e:
                            print("Error procesando línea:", decoded_line)
                            continue
        except Exception as e:
            print(f"Error en la solicitud a ASI1: {e}")
            return None
        '''
        class Dummy:
            def __init__(self, content):
                self.message = type("msg", (), {"content": content})
        return type("Resp", (), {"generations": [[Dummy(output)]]})()
        '''

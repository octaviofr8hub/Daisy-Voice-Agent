# Daisy Voice Agent

- daisy_assistant_fnc.py
- main.py
- daisy_fsm.py
- utils.py
- daisy_prompts.py
- config.py

## Diagrama de contexto (sistema actual):
![DaisyVoiceAgent-v1 drawio](https://github.com/user-attachments/assets/f04e2f38-3887-4e29-b1dc-a1545966260b)

### Desglose de los Puntos del Diagrama

### **Punto 1: User → Twilio Call Service**
- Descripción: El usuario realiza una llamada telefónica al número proporcionado por Twilio Call Service. Este número está configurado para recibir las llamadas entrantes.
- Propósito: Iniciar el proceso al recibir la llamada del usuario, activando el flujo del sistema.

### **Punto 2: Twilio Call Service → Livekit Cloud**
- Descripción: Twilio Call Service transfiere la llamada entrante a LiveKit Cloud. LiveKit se encarga de manejar la conexión de voz en tiempo real (usando WebRTC) y preparar el streaming de audio.
- Propósito: Establecer una conexión bidireccional de audio entre el usuario y el sistema, utilizando LiveKit como intermediario.

### **Punto 3: Livekit Cloud → Voice Agent (Backend)**
- Descripción: LiveKit Cloud envía el audio de la llamada al Voice Agent dentro del backend. El Voice Agent recibe la entrada de voz del usuario y la prepara para ser procesada.
- Propósito: Transmitir el audio del usuario al Voice Agent para que inicie la interacción.

### **Punto 4: Voice Agent → LLM (Backend)**
- Descripción: El Voice Agent envía el audio o texto transcrito (usando OpenAI Realtime API implícitamente) al LLM para que genere una respuesta. El LLM interpreta la intención del usuario y crea un mensaje de voz personalizado.
- Propósito: Procesar la entrada del usuario y generar una respuesta coherente para la conversación.

### **Punto 5: LLM → Voice Agent (Backend)**
- Descripción: El LLM devuelve al Voice Agent la respuesta generada (en forma de texto o audio procesable), que será utilizada para interactuar con el usuario.
- Propósito: Proveer al Voice Agent el contenido de la respuesta para que continúe la conversación.

### **Punto 6: Voice Agent → Livekit Cloud (Backend → Livekit Cloud)**
- Descripción: El Voice Agent envía la respuesta generada (convertida a audio mediante OpenAI Realtime API) a LiveKit Cloud para que se transmita al usuario.
- Propósito: Enviar la respuesta del agente al usuario a través del streaming de audio en tiempo real.

# Instalación

## Requisitos Previos

- **Python 3.10 o superior**
- Una cuenta de **Twilio** con un número de teléfono (habilitado para voz)
- Una cuenta de **LiveKit Cloud**
- Una cuenta de **OpenAI** con acceso a la Realtime API

### 1. Clonar el repositorio

```bash
git clone <url-de-tu-repositorio>
cd <carpeta-de-tu-proyecto>
```

### 2. Configura un Entorno Virtual
Crea y activa un entorno virtual para mantener las dependencias aisladas.

```bash
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
```

### 3. Configurar las variables de entorno
Crear un archivo `.env` y definir las siguientes variables:

```bash
LIVEKIT_URL=""
LIVEKIT_API_KEY=""
LIVEKIT_API_SECRET=""
OPENAI_API_KEY=""
```

### 4. Instalar las dependencias:
En la carpeta raiz ejecutar la siguiente linea:
```bash
pip install -r requirements.txt
```

### Configuramos las reglas:

```json
{
    "name" : "Daisy Demo",
    "trunk_ids" : [""],
    "rule": {
        "dispatchRuleIndividual": {
            "roomPrefix": "call-"
        }
    }
}   
```
```json
{
  "trunk": {
    "name": "My inbound trunk",
    "numbers": ["+1234567890"]
  }
}
```

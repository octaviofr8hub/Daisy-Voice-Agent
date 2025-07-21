from mcp.server.fastmcp import FastMCP
import logging
from fastapi import FastAPI
import os
import json
from pydantic import ( 
    BaseModel, 
    ValidationError, 
    EmailStr 
)
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .email_template import get_email_template, get_email_template_en
from dotenv import load_dotenv

load_dotenv(override=True)

mcp = FastMCP("Demo 🚀")


class DriverDataInput(BaseModel):
    name: str
    tractor_number: str
    tractor_plates: str
    trailer_number: str
    trailer_plates: str
    eta: str
    email: EmailStr

logger = logging.getLogger("mcp-tool")


@mcp.tool()
def get_weather(location: str) -> str:
    return f"The weather in {location} is a perfect sunny 70°F today. Enjoy your day!"


@mcp.tool()
def save_driver_data(data: DriverDataInput) -> str:
    try:
        # Convert Pydantic model to dict for JSON serialization
        #data_dict = data.dict()
        data_dict = data.model_dump()
        with open(f"recolect_data/driver_data_{str(uuid.uuid4())[:5]}.json", "w", encoding="utf-8") as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
        logger.info("Driver data saved: %s", data_dict)
        # Enviar correo
        send_email(data_dict["email"], data_dict)

        return "Datos guardados exitosamente."
    except ValidationError as e:
        logger.error("Validation error for driver data: %s", str(e))
        return f"Error al validar los datos: {str(e)}"
    except Exception as e:
        logger.error("Error saving driver data: %s", str(e))
        return f"Error al guardar los datos: {str(e)}"


def send_email(recipient_email: str, data: dict):
    sender_email = os.getenv("SMTP_SENDER_EMAIL")  # por ejemplo: "tuemail@gmail.com"
    sender_password = os.getenv("SMTP_SENDER_PASSWORD")  # tu contraseña o app password
    smtp_server = "smtp.gmail.com"
    smtp_port = 587

    if not sender_email or not sender_password:
        logger.error("Faltan credenciales SMTP en las variables de entorno")
        raise ValueError("Faltan credenciales SMTP en las variables de entorno")

    '''
    subject = "Confirmación de registro de transporte"
    body = f"""
    Hola {data['name']},

    Tu información ha sido registrada exitosamente:

    - Número de tractor: {data['tractor_number']}
    - Placas del tractor: {data['tractor_plates']}
    - Número del tráiler: {data['trailer_number']}
    - Placas del tráiler: {data['trailer_plates']}
    - ETA: {data['eta']}

    ¡Buen viaje!
    """
    '''
    # Email subject and body
    subject = "Transportation Registration Confirmation"
    body = f"""
    Hello {data['name']},

    Your information has been successfully registered:

    - Tractor Number: {data['tractor_number']}
    - Tractor Plates: {data['tractor_plates']}
    - Trailer Number: {data['trailer_number']}
    - Trailer Plates: {data['trailer_plates']}
    - ETA: {data['eta']}

    Safe travels!
    """

    #html_body = get_email_template(data)
    html_body = get_email_template_en(data)
    msg = MIMEMultipart("alternative")
    msg["From"] = sender_email
    msg["To"] = recipient_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    try:
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)
        server.quit()
        logger.info("Correo enviado a %s", recipient_email)
    except Exception as e:
        logger.error("Error al enviar correo: %s", str(e))



if __name__ == "__main__":
    mcp.run(transport="sse")
def get_email_template(data: dict) -> str:
    """
    Genera el contenido HTML del correo con un diseño atractivo.
    Args:
        data: Diccionario con los datos del transporte (name, tractor_number, etc.).
    Returns:
        Cadena con el contenido HTML del correo.
    """
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Confirmación de Registro de Transporte</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #007bff;
                color: #ffffff;
                padding: 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 20px;
                color: #333333;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.5;
            }}
            .table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            .table th, .table td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #dddddd;
            }}
            .table th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 15px;
                text-align: center;
                font-size: 14px;
                color: #666666;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #007bff;
                color: #ffffff;
                text-decoration: none;
                border-radius: 5px;
                margin: 10px 0;
            }}
            @media only screen and (max-width: 600px) {{
                .container {{
                    width: 100%;
                    margin: 10px;
                }}
                .header h1 {{
                    font-size: 20px;
                }}
                .content p, .table th, .table td {{
                    font-size: 14px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>¡Registro Exitoso!</h1>
            </div>
            <div class="content">
                <p>Hola <strong>{data['name']}</strong>,</p>
                <p>Tu información de transporte ha sido registrada correctamente. Aquí tienes los detalles:</p>
                <table class="table">
                    <tr>
                        <th>Número de Tractor</th>
                        <td>{data['tractor_number']}</td>
                    </tr>
                    <tr>
                        <th>Placas del Tractor</th>
                        <td>{data['tractor_plates']}</td>
                    </tr>
                    <tr>
                        <th>Número del Tráiler</th>
                        <td>{data['trailer_number']}</td>
                    </tr>
                    <tr>
                        <th>Placas del Tráiler</th>
                        <td>{data['trailer_plates']}</td>
                    </tr>
                    <tr>
                        <th>ETA</th>
                        <td>{data['eta']}</td>
                    </tr>
                </table>
                <p>¡Buen viaje y gracias por usar nuestro servicio!</p>
                <a class="button">Ver más detalles</a>
            </div>
            <div class="footer">
                <p>© 2025 Tu Empresa. Todos los derechos reservados.</p>
                <p>¿Preguntas? Contáctanos en <a href="mailto:soporte@tuempresa.com">soporte@tuempresa.com</a></p>
            </div>
        </div>
    </body>
    </html>
    """

def get_email_template_en(data: dict) -> str:
    """
    Generates the HTML content for the email with an attractive design.
    Args:
        data: Dictionary containing transportation data (name, tractor_number, etc.).
    Returns:
        String with the HTML content of the email.
    """
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Transportation Registration Confirmation</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 20px auto;
                background-color: #ffffff;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .header {{
                background-color: #007bff;
                color: #ffffff;
                padding: 20px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 24px;
            }}
            .content {{
                padding: 20px;
                color: #333333;
            }}
            .content p {{
                font-size: 16px;
                line-height: 1.5;
            }}
            .table {{
                width: 100%;
                border-collapse: collapse;
                margin: 20px 0;
            }}
            .table th, .table td {{
                padding: 12px;
                text-align: left;
                border-bottom: 1px solid #dddddd;
            }}
            .table th {{
                background-color: #f8f9fa;
                font-weight: bold;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 15px;
                text-align: center;
                font-size: 14px;
                color: #666666;
            }}
            .button {{
                display: inline-block;
                padding: 12px 24px;
                background-color: #007bff;
                color: #ffffff;
                text-decoration: none;
                border-radius: 5px;
                margin: 10px 0;
            }}
            @media only screen and (max-width: 600px) {{
                .container {{
                    width: 100%;
                    margin: 10px;
                }}
                .header h1 {{
                    font-size: 20px;
                }}
                .content p, .table th, .table td {{
                    font-size: 14px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Registration Successful!</h1>
            </div>
            <div class="content">
                <p>Hello <strong>{data['name']}</strong>,</p>
                <p>Your transportation information has been successfully registered. Here are the details:</p>
                <table class="table">
                    <tr>
                        <th>Tractor Number</th>
                        <td>{data['tractor_number']}</td>
                    </tr>
                    <tr>
                        <th>Tractor Plates</th>
                        <td>{data['tractor_plates']}</td>
                    </tr>
                    <tr>
                        <th>Trailer Number</th>
                        <td>{data['trailer_number']}</td>
                    </tr>
                    <tr>
                        <th>Trailer Plates</th>
                        <td>{data['trailer_plates']}</td>
                    </tr>
                    <tr>
                        <th>ETA</th>
                        <td>{data['eta']}</td>
                    </tr>
                </table>
                <p>Safe travels and thank you for using our service!</p>
                <a class="button">View More Details</a>
            </div>
            <div class="footer">
                <p>© 2025 Your Company. All rights reserved.</p>
                <p>Questions? Contact us at <a href="mailto:support@yourcompany.com">support@yourcompany.com</a></p>
            </div>
        </div>
    </body>
    </html>
    """
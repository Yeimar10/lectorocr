from flask import Flask, request, jsonify
from PIL import Image
import pytesseract
import os
import re
import requests
from io import BytesIO
from twilio.twiml.messaging_response import MessagingResponse

from dotenv import load_dotenv
load_dotenv()

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

# Ruta local a Tesseract OCR
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Crear app Flask
app = Flask(__name__)

# Ruta raíz para verificar el servidor
@app.route('/', methods=['GET'])
def inicio():
    return jsonify({"mensaje": "✅ Servidor Flask funcionando correctamente"})

# OCR desde Postman u otros servicios
@app.route('/subir-imagen', methods=['POST'])
def procesar_imagen():
    if 'imagen' not in request.files:
        return jsonify({"error": "❌ No se encontró ningún archivo llamado 'imagen'"}), 400

    archivo = request.files['imagen']
    if archivo.filename == '':
        return jsonify({"error": "❌ Nombre de archivo vacío"}), 400

    ruta_guardado = "temp.jpg"
    archivo.save(ruta_guardado)

    imagen = Image.open(ruta_guardado)
    texto = pytesseract.image_to_string(imagen, lang='spa')
    datos = extraer_datos(texto)

    return jsonify({
        "mensaje": "✅ Imagen procesada con éxito",
        "texto_ocr": texto,
        "datos_extraidos": datos
    })

# WhatsApp vía Twilio
@app.route('/whatsapp', methods=['POST'])
def whatsapp_webhook():
    mensaje = request.form.get('Body', '').lower()
    media_url = request.form.get('MediaUrl0')
    media_type = request.form.get('MediaContentType0')

    respuesta = MessagingResponse()

    if media_url and 'image' in media_type:
        try:
            respuesta.message("📷 Recibí tu imagen. Procesando OCR...")

            # ✅ Descargar imagen con autenticación de Twilio
            imagen_response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
            imagen = Image.open(BytesIO(imagen_response.content))

            # OCR
            texto = pytesseract.image_to_string(imagen, lang='spa')
            datos = extraer_datos(texto)

            # Armar respuesta
            mensaje_respuesta = "✅ Datos extraídos:\n"
            for k, v in datos.items():
                mensaje_respuesta += f"• {k}: {v}\n"

            if not datos:
                mensaje_respuesta += "⚠️ No se reconocieron datos claves del comprobante."

            respuesta.message(mensaje_respuesta)

        except Exception as e:
            respuesta.message(f"❌ Error procesando la imagen: {str(e)}")

    elif mensaje == 'hola':
        respuesta.message("👋 Hola, soy tu asistente OCR. Envía una imagen de comprobante o escribe 'ayuda'.")
    elif mensaje == 'ayuda':
        respuesta.message("📷 Puedes subir una imagen con comprobante o escribir 'estado' para ver si el servidor está activo.")
    elif mensaje == 'estado':
        respuesta.message("✅ El servidor Flask está funcionando correctamente.")
    else:
        respuesta.message("❌ No entendí tu mensaje. Escribe 'ayuda' para ver opciones.")

    return str(respuesta)

def extraer_datos(texto):
    datos = {}

    # Comprobante
    comprobante = re.search(r'Comprobante No\.?\s*([0-9]{6,})', texto)
    if comprobante:
        datos["Comprobante"] = comprobante.group(1)

    # Fecha y hora
    fecha_hora = re.search(r'(\d{1,2} \w+ \d{4})\s*-\s*(\d{1,2}:\d{2})', texto)
    if fecha_hora:
        datos["Fecha"] = fecha_hora.group(1)
        datos["Hora"] = fecha_hora.group(2)

    # Valor
    valor = re.search(r'Valor de la transferencia\s*\$ ?([\d\.]+)', texto)
    if valor:
        datos["Valor"] = valor.group(1)

    # Destino (Producto destino -> banco -> cuenta)
    destino_match = re.search(
        r'Producto destino\s*\n([^\n]+)\n([^\n]+)', texto, re.IGNORECASE
    )
    if destino_match:
        datos["Producto destino"] = destino_match.group(1).strip()  # Banco o medio (Nequi, Bancolombia, etc.)
        datos["Cuenta destino"] = destino_match.group(2).strip().replace(" ", "").replace("-", "")

    # Origen (Producto origen -> tipo -> cuenta)
    origen_match = re.search(
        r'Producto origen\s+([^\n]+)\n.*?(\*?\d{4})', texto, re.DOTALL | re.IGNORECASE
    )
    if origen_match:
        datos["Producto origen"] = origen_match.group(1).strip()
        datos["Cuenta origen"] = origen_match.group(2).strip()

    return datos


# Ejecutar
if __name__ == '__main__':
    app.run(debug=True)
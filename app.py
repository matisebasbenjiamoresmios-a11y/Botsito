from flask import Flask, request, jsonify, send_file
import requests
import os
import PyPDF2
import docx

app = Flask(__name__)

# Clave de OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_OPENAI = "mistralai/mistral-7b-instruct:free"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "index.html"))

@app.route("/robots.txt")
def robots_txt():
    return send_file("robots.txt")


@app.route("/sitemap.xml")
def sitemap_map():
    return send_file("sitemap.xml")

@app.route("/preguntar", methods=["POST"])
def ask():
    data = request.get_json()
    user_msg = data.get("pregunta", "")
    from bot_core import responder_pregunta
    bot_reply = responder_pregunta(user_msg)
    return jsonify({"respuesta": bot_reply})

@app.route("/upload", methods=["POST"])
def upload():
    if 'archivo' not in request.files:
        return jsonify({"resumen": ["⚠️ No se envió ningún archivo."]})

    archivo = request.files['archivo']
    nombre = archivo.filename
    extension = nombre.split('.')[-1].lower()

    try:
        # Leer contenido según tipo
        if extension == "pdf":
            reader = PyPDF2.PdfReader(archivo)
            texto = " ".join(page.extract_text() for page in reader.pages if page.extract_text())
        elif extension == "txt":
            texto = archivo.read().decode("utf-8")
        elif extension == "docx":
            doc = docx.Document(archivo)
            texto = " ".join(p.text for p in doc.paragraphs)
        else:
            return jsonify({"resumen": ["❌ Formato no soportado. Usa PDF, DOCX o TXT."]})

        # Dividir en partes de 1500 caracteres
        partes = [texto[i:i + 1500] for i in range(0, len(texto), 1500)]

        partes_resumen = []
        for idx, parte in enumerate(partes, 1):
            resumen = resumir_con_modelo(parte)
            partes_resumen.append(resumen)

        return jsonify({"resumen": partes_resumen})

    except Exception as e:
        return jsonify({"resumen": [f"⚠️ Error al procesar el archivo: {str(e)}"]})

def resumir_con_modelo(texto):
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost",
                "X-Title": "BotsitoIA"
            },
            json={
                "model": MODEL_OPENAI,
                "messages": [
                    {"role": "user", "content": f"Resume este texto en español:\n{texto}"}
                ]
            },
            timeout=60
        )

        if response.status_code != 200:
            return f"⚠️ Error {response.status_code} - {response.text[:100]}"

        data = response.json()
        return data['choices'][0]['message']['content']

    except Exception as e:
        return f"⚠️ Error al resumir: {str(e)}"

if __name__ == "__main__":
    # Render asigna el puerto en la variable de entorno PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

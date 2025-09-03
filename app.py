from flask import Flask, request, jsonify, send_file
import os
import requests
import PyPDF2
import docx

from bot_core import responder_pregunta

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_OPENAI = "mistralai/mistral-7b-instruct:free"

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        user_msg = data.get("pregunta", "")
        print("📩 Recibido:", user_msg)
        bot_reply = responder_pregunta(user_msg)
        return jsonify({"response": bot_reply})
    except Exception as e:
        return jsonify({"response": f"⚠️ Error al procesar la pregunta: {str(e)}"})

@app.route("/reset", methods=["POST"])
def reset():
    return jsonify({"response": "🧹 Memoria interna reseteada."})

@app.route("/upload", methods=["POST"])
def upload():
    try:
        if 'file' not in request.files:
            return jsonify({"message": "⚠️ No se envió ningún archivo."})

        file = request.files['file']
        filename = file.filename
        ext = filename.split('.')[-1].lower()

        if ext == "pdf":
            reader = PyPDF2.PdfReader(file)
            text = " ".join(page.extract_text() or "" for page in reader.pages)
        elif ext == "txt":
            text = file.read().decode("utf-8")
        elif ext == "docx":
            doc = docx.Document(file)
            text = " ".join(p.text for p in doc.paragraphs)
        else:
            return jsonify({"message": "❌ Formato no soportado."})

        partes = [text[i:i+2000] for i in range(0, len(text), 2000)]
        resumen = ""
        for idx, parte in enumerate(partes):
            resumen_parcial = resumir_con_modelo(parte)
            resumen += f"\n\n📄 Parte {idx+1}:\n{resumen_parcial}"

        return jsonify({"message": resumen})
    except Exception as e:
        return jsonify({"message": f"⚠️ Error procesando archivo: {str(e)}"})

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
            return f"⚠️ Error OpenRouter: {response.status_code}"

        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Error al resumir: {str(e)}"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

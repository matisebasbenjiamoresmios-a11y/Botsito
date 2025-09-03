from flask import Flask, request, jsonify, send_file
import requests
import os
import PyPDF2
import docx

app = Flask(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_OPENAI = "mistralai/mistral-7b-instruct:free"

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    try:
        user_msg = request.get_json().get("message")
        print("📩 Recibido:", user_msg)
        from bot_core import responder_pregunta
        bot_reply = responder_pregunta(user_msg)
        return jsonify({"response": bot_reply})
    except Exception as e:
        return jsonify({"response": f"⚠️ Error al procesar la pregunta: {str(e)}"})

@app.route("/reset", methods=["POST"])
def reset():
    return jsonify({"response": "🧹 Memoria interna reseteada."})

@app.route("/upload", methods=["POST"])
def upload():
    if 'file' not in request.files:
        return jsonify({"message": "⚠️ No se envió ningún archivo."})
    
    file = request.files['file']
    filename = file.filename
    ext = filename.split('.')[-1].lower()

    try:
        if ext == "pdf":
            reader = PyPDF2.PdfReader(file)
            text = " ".join(page.extract_text() for page in reader.pages if page.extract_text())
        elif ext == "txt":
            text = file.read().decode("utf-8")
        elif ext == "docx":
            doc = docx.Document(file)
            text = " ".join(p.text for p in doc.paragraphs)
        else:
            return jsonify({"message": "❌ Formato no soportado."})

        part_size = 2000
        parts = [text[i:i + part_size] for i in range(0, len(text), part_size)]

        resumen_total = ""
        for idx, part in enumerate(parts, 1):
            resumen = resumir_con_modelo(part)
            resumen_total += f"\n\n📄 Resumen parte {idx}/{len(parts)}:\n{resumen}"

        return jsonify({"message": resumen_total})
    except Exception as e:
        return jsonify({"message": f"⚠️ Error al procesar archivo: {str(e)}"})

def resumir_con_modelo(texto_parte):
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
                    {"role": "user", "content": f"Resume este texto en español:\n{texto_parte}"}
                ]
            },
            timeout=60
        )

        if response.status_code != 200:
            return f"⚠️ Error de OpenRouter: {response.status_code} - {response.text[:100]}"

        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Error al resumir parte: {str(e)}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

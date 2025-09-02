from flask import Flask, request, jsonify, send_file
import requests
import os
import PyPDF2
import docx

app = Flask(__name__)

# 🔑 Clave de OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
MODEL_OPENAI = "mistralai/mistral-7b-instruct:free"

@app.route("/check-key")
def check_key():
    import os
    key = os.environ.get("OPENROUTER_API_KEY")
    return f"Clave encontrada: {key[:10]}..." if key else "❌ NO encontrada"

@app.route("/")
def index():
    return send_file("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_msg = request.data.decode("utf-8")
    print("📩 Recibido:", user_msg) #NUEVO
    from bot_core import responder_pregunta
    bot_reply = responder_pregunta(user_msg)
    return jsonify({"response": bot_reply})

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
        # 1. Leer archivo
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

        # 2. Dividir en partes para no saturar el modelo
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
    """Llama a OpenRouter para resumir un texto en español"""
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
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"⚠️ Error al resumir parte: {str(e)}"

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)

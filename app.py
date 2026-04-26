from flask import Flask, request, jsonify, send_file, make_response
import os
import PyPDF2
import docx
import tempfile
from openai import OpenAI

app = Flask(__name__)

# ===== CONFIG =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MODEL_OPENAI = "gpt-4o-mini"        # más rápido
TTS_MODEL = "gpt-4o-mini-tts"       # voz rápida
TTS_VOICE = "alloy"                 # voz más veloz

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ===== HOME =====
@app.route("/")
def index():
    resp = make_response(send_file(os.path.join(BASE_DIR, "index.html")))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return resp


@app.route("/robots.txt")
def robots_txt():
    return send_file(os.path.join(BASE_DIR, "robots.txt"), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_map():
    return send_file(os.path.join(BASE_DIR, "sitemap.xml"), mimetype="application/xml")


# ===== CHAT =====
@app.route("/preguntar", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        user_msg = (data or {}).get("pregunta", "").strip()

        if not user_msg:
            return jsonify({"respuesta": "No escuché la pregunta."})

        from bot_core import responder_pregunta
        bot_reply = responder_pregunta(user_msg)

        return jsonify({"respuesta": bot_reply})

    except Exception as e:
        return jsonify({"respuesta": f"⚠️ Error: {str(e)}"}), 500


# ===== VOZ =====
@app.route("/voz", methods=["POST"])
def voz():
    try:
        data = request.get_json()
        texto = (data or {}).get("texto", "").strip()

        if not texto:
            return jsonify({"error": "Sin texto"}), 400

        speech = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=texto
        )

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_file.write(speech.content)
        temp_file.close()

        return send_file(temp_file.name, mimetype="audio/mpeg")

    except Exception as e:
        return jsonify({"error": f"Error voz: {str(e)}"}), 500


# ===== ARCHIVOS =====
@app.route("/upload", methods=["POST"])
def upload():
    try:
        if 'archivo' not in request.files:
            return jsonify({"resumen": ["⚠️ No se envió archivo."]})

        archivo = request.files['archivo']
        nombre = archivo.filename or ""
        extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ""

        texto = ""

        if extension == "pdf":
            reader = PyPDF2.PdfReader(archivo.stream)
            texto = " ".join((p.extract_text() or "") for p in reader.pages)

        elif extension == "txt":
            texto = archivo.read().decode("utf-8", errors="ignore")

        elif extension == "docx":
            doc = docx.Document(archivo)
            texto = " ".join(p.text for p in doc.paragraphs)

        else:
            return jsonify({"resumen": ["❌ Formato no soportado."]})

        if not texto.strip():
            return jsonify({"resumen": ["⚠️ Archivo sin texto."]})

        partes = [texto[i:i + 500] for i in range(0, len(texto), 500)]

        resultados = []
        for parte in partes:
            resultados.append(resumir_con_modelo(parte))

        return jsonify({"resumen": resultados})

    except Exception as e:
        return jsonify({"resumen": [f"⚠️ Error: {str(e)}"]}), 500


# ===== RESUMEN IA =====
def resumir_con_modelo(texto):
    try:
        response = client.chat.completions.create(
            model=MODEL_OPENAI,
            messages=[
                {"role": "user", "content": f"Resumí esto en español en pocas líneas:\n{texto}"}
            ],
            temperature=0.4,
            max_tokens=120
        )

        return response.choices[0].message.content.strip()

    except Exception as e:
        return f"⚠️ Error IA: {e}"


# ===== RUN =====
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
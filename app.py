from flask import Flask, request, jsonify, send_file, make_response
import requests
import os
import PyPDF2
import docx

app = Flask(__name__)

# ===== OpenAI (antes: OpenRouter) =====
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_OPENAI = "gpt-4o"  # puedes cambiar a "gpt-4o" si tienes acceso

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    resp = make_response(send_file(os.path.join(BASE_DIR, "index.html")))
    # (solo para ver cambios al instante; no altera la lógica)
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@app.route("/robots.txt")
def robots_txt():
    return send_file(os.path.join(BASE_DIR, "robots.txt"), mimetype="text/plain")


@app.route("/sitemap.xml")
def sitemap_map():
    return send_file(os.path.join(BASE_DIR, "sitemap.xml"), mimetype="application/xml")


@app.route("/preguntar", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        user_msg = (data or {}).get("pregunta", "")
        from bot_core import responder_pregunta
        bot_reply = responder_pregunta(user_msg)
        return jsonify({"respuesta": bot_reply})
    except Exception as e:
        return jsonify({"respuesta": f"⚠️ Error al procesar la pregunta: {str(e)}"}), 500


@app.route("/upload", methods=["POST"])
def upload():
    try:
        if 'archivo' not in request.files:
            return jsonify({"resumen": ["⚠️ No se envió ningún archivo."]})

        archivo = request.files['archivo']
        nombre = archivo.filename or ""
        extension = nombre.rsplit('.', 1)[-1].lower() if '.' in nombre else ""

        # Leer contenido según tipo (misma lógica)
        texto = ""
        if extension == "pdf":
            archivo.stream.seek(0)
            reader = PyPDF2.PdfReader(archivo.stream)
            texto = " ".join((page.extract_text() or "") for page in reader.pages)
        elif extension == "txt":
            archivo.stream.seek(0)
            texto = archivo.read().decode("utf-8", errors="ignore")
        elif extension == "docx":
            archivo.stream.seek(0)
            doc = docx.Document(archivo)
            texto = " ".join(p.text for p in doc.paragraphs)
        else:
            return jsonify({"resumen": ["❌ Formato no soportado. Usa PDF, DOCX o TXT."]})

        texto = (texto or "").strip()
        if not texto:
            return jsonify({"resumen": ["⚠️ El archivo no contiene texto legible."]})

        # Partes de 1500 caracteres (igual que antes)
        partes = [texto[i:i + 1500] for i in range(0, len(texto), 1500)] or [""]

        partes_resumen = []
        for parte in partes:
            resumen = resumir_con_modelo(parte)
            partes_resumen.append(resumen)

        return jsonify({"resumen": partes_resumen})

    except Exception as e:
        return jsonify({"resumen": [f"⚠️ Error al procesar el archivo: {str(e)}"]}), 500


def resumir_con_modelo(texto):
    """Llama al endpoint oficial de OpenAI (chat.completions)."""
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL_OPENAI,
                "messages": [
                    {"role": "user", "content": f"Resume este texto en español:\n{texto}"}
                ]
            },
            timeout=(15, 180)  # conexión, lectura (seguro ante respuestas lentas)
        )

        if response.status_code != 200:
            return f"⚠️ Error {response.status_code} - {response.text[:120]}"

        data = response.json()
        return data['choices'][0]['message']['content']

    except Exception as e:
        return f"⚠️ Error al resumir: {str(e)}"


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

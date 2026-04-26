from flask import Flask, request, jsonify, send_file, make_response, Response, stream_with_context
import requests
import os
import PyPDF2
import docx
import tempfile
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_OPENAI = "gpt-4o-mini"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "alloy"

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    resp = make_response(send_file(os.path.join(BASE_DIR, "index.html")))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# 🔥 STREAMING NUEVO
@app.route("/stream", methods=["POST"])
def stream():
    data = request.get_json()
    pregunta = (data or {}).get("pregunta", "")

    def generar():
        try:
            stream = client.chat.completions.create(
                model=MODEL_OPENAI,
                messages=[
                    {"role": "system", "content": "Respondé corto, claro y natural."},
                    {"role": "user", "content": pregunta}
                ],
                stream=True,
                max_tokens=90
            )

            for chunk in stream:
                if chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content

        except Exception as e:
            yield f"Error: {e}"

    return Response(stream_with_context(generar()), mimetype="text/plain")


@app.route("/preguntar", methods=["POST"])
def ask():
    data = request.get_json()
    user_msg = (data or {}).get("pregunta", "")

    from bot_core import responder_pregunta
    bot_reply = responder_pregunta(user_msg)

    return jsonify({"respuesta": bot_reply})


@app.route("/voz", methods=["POST"])
def voz():
    data = request.get_json()
    texto = (data or {}).get("texto", "").strip()

    speech = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=texto
    )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_file.write(speech.content)
    temp_file.close()

    return send_file(temp_file.name, mimetype="audio/mpeg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
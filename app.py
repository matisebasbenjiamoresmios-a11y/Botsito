from flask import Flask, request, Response, stream_with_context, send_file
import os
from openai import OpenAI

app = Flask(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

MODEL = "gpt-4o-mini"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "alloy"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


@app.route("/")
def index():
    return send_file(os.path.join(BASE_DIR, "index.html"))


# 🔥 STREAM DE TEXTO (tipo ChatGPT en vivo)
@app.route("/stream", methods=["POST"])
def stream():
    data = request.get_json()
    pregunta = data.get("pregunta", "")

    def generar():
        try:
            with client.chat.completions.stream(
                model=MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "Respondé en español, máximo 2 oraciones, claro y directo."
                    },
                    {"role": "user", "content": pregunta}
                ],
                temperature=0.4,
                max_tokens=80
            ) as stream:

                for event in stream:
                    if event.type == "content.delta":
                        yield event.delta

        except Exception as e:
            yield f"Error: {e}"

    return Response(stream_with_context(generar()), mimetype="text/plain")


# 🔊 VOZ (igual pero optimizado)
@app.route("/voz", methods=["POST"])
def voz():
    data = request.get_json()
    texto = data.get("texto", "")

    speech = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=texto
    )

    path = "voz.mp3"
    with open(path, "wb") as f:
        f.write(speech.content)

    return send_file(path, mimetype="audio/mpeg")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
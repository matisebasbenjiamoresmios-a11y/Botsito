from flask import Flask, request, jsonify, send_file, make_response, Response, stream_with_context
import requests
import wave
import json
import os
import PyPDF2
import docx
import tempfile
import re
from array import array
from openai import OpenAI

app = Flask(__name__)


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_OPENAI = "gpt-4o-mini"
TTS_MODEL = "gpt-4o-mini-tts"
TTS_VOICE = "alloy"

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "xf3Xv0R9rgFTExG0MVNo")

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

AUDIO_DIR = os.path.join(BASE_DIR, "tts")
NOMBRE_ULTIMO_AUDIO = "ultima_respuesta.mp3"
RUTA_ULTIMO_AUDIO = os.path.join(AUDIO_DIR, NOMBRE_ULTIMO_AUDIO)

os.makedirs(AUDIO_DIR, exist_ok=True)


def extraer_pregunta_activada(texto):
    """
    Detecta "Hey Baifo" u "Oye Baifo" y variantes comunes
    producidas por la transcripción. Devuelve (activado, pregunta).
    """
    texto = (texto or "").strip()

    if not texto:
        return False, ""

    patron = re.compile(
        r"\b(?:hey|ey|oye|hoy)\b[\s,.;:¡!¿?\\-]*(?:baifo|waifo|weifo|wifo|wifi|wi[\s-]?fi|guifo|byfo|vaifo|bifo)\b",
        re.IGNORECASE
    )

    coincidencia = patron.search(texto)

    if not coincidencia:
        return False, ""

    pregunta = texto[coincidencia.end():].strip(" \t\r\n,.;:¿?¡!-")
    return True, pregunta




def amplificar_pcm16(datos_pcm, objetivo_pico=24000, ganancia_maxima=12.0):
    """Normaliza audio PCM mono de 16 bits sin usar librerías externas."""
    if not datos_pcm:
        return datos_pcm, 0, 0, 1.0

    muestras = array("h")
    muestras.frombytes(datos_pcm)

    if os.sys.byteorder != "little":
        muestras.byteswap()

    pico_original = max((abs(int(m)) for m in muestras), default=0)

    if pico_original == 0:
        return datos_pcm, 0, 0, 1.0

    ganancia = min(ganancia_maxima, objetivo_pico / pico_original)

    for i, muestra in enumerate(muestras):
        valor = int(muestra * ganancia)
        if valor > 32767:
            valor = 32767
        elif valor < -32768:
            valor = -32768
        muestras[i] = valor

    pico_final = max((abs(int(m)) for m in muestras), default=0)

    if os.sys.byteorder != "little":
        muestras.byteswap()

    return muestras.tobytes(), pico_original, pico_final, ganancia


def eliminar_archivo_si_existe(ruta):
    if os.path.exists(ruta):
        os.remove(ruta)


@app.route("/")
def index():
    resp = make_response(send_file(os.path.join(BASE_DIR, "index.html")))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# STREAMING NUEVO
@app.route("/stream", methods=["POST"])
def stream():
    data = request.get_json()
    pregunta = (data or {}).get("pregunta", "")

    def generar():
        try:
            stream = client.chat.completions.create(
                model=MODEL_OPENAI,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Respondé corto, claro y natural. "
                            "Si el usuario pide código, generá el código ordenado en bloques con triple comilla ``` "
                            "y no agregues explicación larga salvo que la pidan."
                        )
                    },
                    {"role": "user", "content": pregunta}
                ],
                stream=True,
                max_tokens=200
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


@app.route("/ping", methods=["GET"])
def ping():
    return jsonify({
        "estado": "ok",
        "mensaje": "Hola ESP32"
    })

@app.route("/voz", methods=["POST"])
def voz():
    data = request.get_json()
    texto = (data or {}).get("texto", "").strip()

    if not texto:
        return jsonify({"error": "Texto vacío"}), 400

    if ELEVENLABS_API_KEY:
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"

        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }

        body = {
            "text": texto,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {
                "stability": 0.55,
                "similarity_boost": 0.85,
                "style": 0.25,
                "use_speaker_boost": True
            }
        }

        r = requests.post(url, json=body, headers=headers, timeout=60)

        if r.status_code != 200:
            return jsonify({"error": r.text}), 500

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        temp_file.write(r.content)
        temp_file.close()

        return send_file(temp_file.name, mimetype="audio/mpeg")

    speech = client.audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=texto
    )

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
    temp_file.write(speech.content)
    temp_file.close()

    return send_file(temp_file.name, mimetype="audio/mpeg")


# ===========================
# RECIBIR AUDIO DESDE ESP32
# ===========================
# ===========================
# RECIBIR AUDIO DESDE ESP32
# ===========================
@app.route("/audio", methods=["POST"])
def recibir_audio():

    session = request.args.get("session")
    final = request.args.get("final", "0")

    if not session:
        return jsonify({
            "estado": "error",
            "mensaje": "Falta session"
        }), 400

    audio = request.get_data()

    if not audio:
        return jsonify({
            "estado": "error",
            "mensaje": "No se recibieron datos"
        }), 400

    os.makedirs("uploads", exist_ok=True)

    raw_path = os.path.join(
        "uploads",
        f"{session}.raw"
    )

    # Agregar el bloque recibido
    with open(raw_path, "ab") as f:
        f.write(audio)

    # Si todavía no terminó la grabación,
    # solamente confirmar recepción.
    if final != "1":

        return jsonify({
            "estado": "recibiendo",
            "mensaje": "Bloque recibido"
        })
        

    # ======================================
    # A partir de aquí comienza la segunda
    # parte que te pasaré en el siguiente mensaje.
    # ======================================
    
    wav_path = os.path.join(
        "uploads",
        f"{session}.wav"
    )

    with open(raw_path, "rb") as raw:
        datos_raw = raw.read()

    datos_amplificados, pico_original, pico_final, ganancia_aplicada = amplificar_pcm16(datos_raw)

    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(datos_amplificados)

    try:

        print(f"Archivo WAV: {wav_path}")

        with open(wav_path, "rb") as f:

            transcripcion = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f,
                language="es"
            )

        texto_transcrito = (transcripcion.text or "").strip()

        # Nunca enviar a GPT una transcripción vacía.
        if not texto_transcrito:
            print("\n==============================")
            print("DIAGNÓSTICO WHISPER")
            print("==============================")
            print(f"Tamaño WAV: {os.path.getsize(wav_path)} bytes")
            print(f"Pico original PCM: {pico_original}")
            print(f"Ganancia aplicada: {ganancia_aplicada:.2f}x")
            print(f"Pico final PCM: {pico_final}")
            print("Texto recibido: ''")
            print("==============================\n")

            eliminar_archivo_si_existe(raw_path)
            eliminar_archivo_si_existe(wav_path)

            return jsonify({
                "estado": "sin_audio",
                "transcripcion": "",
                "mensaje": "Whisper no detectó ninguna voz"
            })

        print("\n==============================")
        print("DIAGNÓSTICO WHISPER")
        print("==============================")
        print(f"Tamaño WAV: {os.path.getsize(wav_path)} bytes")
        print(f"Pico original PCM: {pico_original}")
        print(f"Ganancia aplicada: {ganancia_aplicada:.2f}x")
        print(f"Pico final PCM: {pico_final}")
        print(f"Texto recibido: '{texto_transcrito}'")
        print("==============================\n")

        activado, pregunta = extraer_pregunta_activada(texto_transcrito)

        if not activado:
            eliminar_archivo_si_existe(raw_path)
            eliminar_archivo_si_existe(wav_path)

            return jsonify({
                "estado": "sin_activacion",
                "transcripcion": texto_transcrito,
                "mensaje": "No se detectó Hey Baifo ni Oye Baifo"
            })

        if not pregunta:
            eliminar_archivo_si_existe(raw_path)
            eliminar_archivo_si_existe(wav_path)

            return jsonify({
                "estado": "sin_pregunta",
                "transcripcion": texto_transcrito,
                "mensaje": "Se detectó la activación, pero no una pregunta"
            })

        from bot_core import responder_pregunta

        print("\n==============================")
        print("DIAGNÓSTICO GPT")
        print("==============================")
        print(f"Pregunta enviada a GPT: {pregunta!r}")
        print("==============================\n")

        respuesta = responder_pregunta(pregunta)

        speech = client.audio.speech.create(
            model=TTS_MODEL,
            voice=TTS_VOICE,
            input=respuesta
        )

        # Guardar siempre la respuesta más reciente con el mismo nombre.
        # Primero se escribe en un archivo temporal y luego se reemplaza
        # para evitar que se sirva un MP3 incompleto.
        ruta_temporal = RUTA_ULTIMO_AUDIO + ".tmp"

        with open(ruta_temporal, "wb") as f:
            f.write(speech.content)

        os.replace(ruta_temporal, RUTA_ULTIMO_AUDIO)

        eliminar_archivo_si_existe(raw_path)
        eliminar_archivo_si_existe(wav_path)

        return jsonify({
            "estado": "ok",
            "transcripcion": texto_transcrito,
            "pregunta": pregunta,
            "texto": respuesta,
            "audio": request.host_url + "tts/" + NOMBRE_ULTIMO_AUDIO
        })

    except Exception as e:
        eliminar_archivo_si_existe(raw_path)
        eliminar_archivo_si_existe(wav_path)

        return jsonify({
            "estado": "error",
            "mensaje": str(e)
        }), 500
    
    
        
@app.route("/tts/ultima_respuesta.mp3")
def servir_ultima_respuesta():
    if not os.path.isfile(RUTA_ULTIMO_AUDIO):
        return jsonify({
            "estado": "error",
            "mensaje": "Todavía no existe una respuesta de audio"
        }), 404

    respuesta_audio = make_response(send_file(
        RUTA_ULTIMO_AUDIO,
        mimetype="audio/mpeg",
        conditional=True
    ))

    respuesta_audio.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    respuesta_audio.headers["Pragma"] = "no-cache"
    respuesta_audio.headers["Expires"] = "0"

    return respuesta_audio

    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
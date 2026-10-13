
from flask import (
    Flask, request, jsonify, send_file,
    make_response, Response, stream_with_context
)

import os
import re
import json
import wave
import time
import tempfile
import requests

from array import array
from threading import Lock
from openai import OpenAI


app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "tts")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")

os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ============================================
# CONFIGURACION OPENAI
# ============================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

MODEL_OPENAI = os.getenv(
    "BAIFO_GPT_MODEL", "gpt-4o-mini"
)

TTS_MODEL = os.getenv(
    "BAIFO_TTS_MODEL", "tts-1"
)

TTS_VOICE = os.getenv(
    "BAIFO_TTS_VOICE", "alloy"
)

TRANSCRIBE_MODEL = os.getenv(
    "BAIFO_TRANSCRIBE_MODEL",
    "gpt-4o-mini-transcribe"
)


# ============================================
# CONFIGURACION ELEVENLABS
# ============================================

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

ELEVENLABS_VOICE_ID = os.getenv(
    "ELEVENLABS_VOICE_ID",
    "xf3Xv0R9rgFTExG0MVNo"
)

ELEVENLABS_MODEL = os.getenv(
    "ELEVENLABS_MODEL",
    "eleven_multilingual_v2"
)


client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=45.0,
    max_retries=0
)


# ============================================
# ARCHIVOS Y CONTROL
# ============================================

NOMBRE_ULTIMO_AUDIO = "ultima_respuesta.mp3"

RUTA_ULTIMO_AUDIO = os.path.join(
    AUDIO_DIR, NOMBRE_ULTIMO_AUDIO
)

CONTROL_BAIFO_PATH = os.path.join(
    BASE_DIR, "baifo_control.json"
)

control_lock = Lock()
audio_lock = Lock()


def log(mensaje):
    print(mensaje, flush=True)


def eliminar_archivo_si_existe(ruta):
    try:
        if os.path.isfile(ruta):
            os.remove(ruta)
    except OSError as e:
        log(f"[BAIFO] Error eliminando archivo: {e}")


# ============================================
# BOTON VIRTUAL
# ============================================

def leer_control_baifo():
    try:
        with control_lock:
            with open(
                CONTROL_BAIFO_PATH,
                "r",
                encoding="utf-8"
            ) as f:
                data = json.load(f)

            return bool(data.get("activo", False))

    except Exception:
        return False


def guardar_control_baifo(activo):
    temporal = CONTROL_BAIFO_PATH + ".tmp"

    with control_lock:
        with open(
            temporal,
            "w",
            encoding="utf-8"
        ) as f:
            json.dump({"activo": bool(activo)}, f)

        os.replace(temporal, CONTROL_BAIFO_PATH)


@app.route("/baifo/control", methods=["GET", "POST"])
def control_baifo():

    if request.method == "POST":
        data = request.get_json(silent=True) or {}

        if "activo" not in data:
            return jsonify({
                "estado": "error",
                "mensaje": "Falta el campo activo"
            }), 400

        activo = data["activo"]

        if not isinstance(activo, bool):
            return jsonify({
                "estado": "error",
                "mensaje": "activo debe ser verdadero o falso"
            }), 400

        guardar_control_baifo(activo)

        log(
            "[BAIFO CONTROL] " +
            ("ENCENDIDO" if activo else "APAGADO")
        )

        return jsonify({
            "estado": "ok",
            "activo": activo
        })

    return jsonify({
        "estado": "ok",
        "activo": leer_control_baifo()
    })


# ============================================
# DETECCION DE FRASE
# SE CONSERVA DEL CODIGO ANTERIOR
# ============================================

def extraer_pregunta_activada(texto):
    texto = (texto or "").strip()

    patron = re.compile(
        r"\b(?:hey|ey|oye|hoy)\b"
        r"[\s,.;:¡!¿?\-]*"
        r"(?:baifo|waifo|weifo|wifo|wifi|wi[\s-]?fi|"
        r"guifo|byfo|vaifo|bifo)\b",
        re.IGNORECASE
    )

    coincidencia = patron.search(texto)

    if not coincidencia:
        return False, ""

    pregunta = texto[coincidencia.end():].strip(
        " \t\r\n,.;:¿?¡!-"
    )

    return True, pregunta


# ============================================
# AMPLIFICACION DE AUDIO
# ============================================

def amplificar_pcm16(
    datos_pcm,
    objetivo_pico=24000,
    ganancia_maxima=12.0
):

    if not datos_pcm:
        return datos_pcm, 0, 0, 1.0

    muestras = array("h")
    muestras.frombytes(datos_pcm)

    if os.sys.byteorder != "little":
        muestras.byteswap()

    pico_original = max(
        (abs(int(m)) for m in muestras),
        default=0
    )

    if pico_original == 0:
        return datos_pcm, 0, 0, 1.0

    ganancia = min(
        ganancia_maxima,
        objetivo_pico / pico_original
    )

    for i, muestra in enumerate(muestras):
        valor = int(muestra * ganancia)
        muestras[i] = max(-32768, min(32767, valor))

    pico_final = max(
        (abs(int(m)) for m in muestras),
        default=0
    )

    if os.sys.byteorder != "little":
        muestras.byteswap()

    return (
        muestras.tobytes(),
        pico_original,
        pico_final,
        ganancia
    )


# ============================================
# PAGINA PRINCIPAL
# ============================================

@app.route("/")
def index():

    ruta = os.path.join(BASE_DIR, "index.html")

    if not os.path.isfile(ruta):
        return jsonify({
            "estado": "ok",
            "mensaje": "Servidor Baifo activo"
        })

    resp = make_response(send_file(ruta))
    resp.headers["Cache-Control"] = "no-store"

    return resp


@app.route("/ping")
def ping():
    return jsonify({
        "estado": "ok",
        "mensaje": "Hola ESP32"
    })


# ============================================
# PREGUNTAS POR TEXTO
# ============================================

@app.route("/preguntar", methods=["POST"])
def preguntar():

    from bot_core import responder_pregunta

    data = request.get_json(silent=True) or {}
    pregunta = str(data.get("pregunta", ""))

    respuesta = responder_pregunta(pregunta)

    return jsonify({"respuesta": respuesta})


# ============================================
# STREAM DE TEXTO
# ============================================

@app.route("/stream", methods=["POST"])
def stream():

    data = request.get_json(silent=True) or {}
    pregunta = str(data.get("pregunta", ""))

    def generar():
        try:
            flujo = client.chat.completions.create(
                model=MODEL_OPENAI,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres Baifo. Responde en español, "
                            "de forma breve, clara y natural."
                        )
                    },
                    {
                        "role": "user",
                        "content": pregunta
                    }
                ],
                max_completion_tokens=200,
                stream=True
            )

            for chunk in flujo:
                contenido = chunk.choices[0].delta.content

                if contenido:
                    yield contenido

        except Exception as e:
            log(f"[BAIFO STREAM] ERROR: {e}")
            yield "No pude generar la respuesta."

    return Response(
        stream_with_context(generar()),
        mimetype="text/plain"
    )


# ============================================
# GENERACION DE VOZ
# ELEVENLABS PRINCIPAL
# OPENAI COMO RESPALDO
# ============================================

def generar_mp3(texto):

    inicio = time.monotonic()

    # PRIMERO: ELEVENLABS
    if ELEVENLABS_API_KEY:

        try:
            log("[BAIFO] Generando voz con ElevenLabs...")

            url = (
                "https://api.elevenlabs.io/v1/text-to-speech/"
                + ELEVENLABS_VOICE_ID
            )

            respuesta = requests.post(
                url,
                headers={
                    "xi-api-key": ELEVENLABS_API_KEY,
                    "Content-Type": "application/json",
                    "Accept": "audio/mpeg"
                },
                json={
                    "text": texto,
                    "model_id": ELEVENLABS_MODEL,
                    "output_format": "mp3_44100_128"
                },
                timeout=45
            )

            respuesta.raise_for_status()

            datos_mp3 = respuesta.content

            if not datos_mp3:
                raise ValueError(
                    "ElevenLabs devolvio audio vacio"
                )

            duracion = time.monotonic() - inicio

            log(
                f"[BAIFO TIEMPOS] ElevenLabs: "
                f"{duracion:.2f} s"
            )

            log(
                f"[BAIFO] MP3 ElevenLabs: "
                f"{len(datos_mp3)} bytes"
            )

            return datos_mp3

        except Exception as e:

            log(f"[BAIFO] ElevenLabs fallo: {e}")
            log(
                "[BAIFO] Usando OpenAI "
                "como respaldo..."
            )

    else:
        log(
            "[BAIFO] No hay API Key de ElevenLabs. "
            "Usando OpenAI TTS."
        )

    # SEGUNDO: OPENAI COMO RESPALDO
    speech = client.with_options(
        timeout=45.0,
        max_retries=0
    ).audio.speech.create(
        model=TTS_MODEL,
        voice=TTS_VOICE,
        input=texto,
        response_format="mp3"
    )

    duracion = time.monotonic() - inicio

    log(
        f"[BAIFO TIEMPOS] OpenAI TTS: "
        f"{duracion:.2f} s"
    )

    return speech.content


# ============================================
# GUARDAR AUDIO MP3
# ============================================

def guardar_mp3(datos):

    if not datos:
        raise ValueError(
            "El MP3 generado esta vacio"
        )

    temporal = RUTA_ULTIMO_AUDIO + ".tmp"

    with audio_lock:
        with open(temporal, "wb") as f:
            f.write(datos)

        os.replace(
            temporal,
            RUTA_ULTIMO_AUDIO
        )

    log(
        f"[BAIFO] MP3 guardado: "
        f"{len(datos)} bytes"
    )


# ============================================
# RUTA /VOZ
# ============================================

@app.route("/voz", methods=["POST"])
def voz():

    data = request.get_json(silent=True) or {}
    texto = str(data.get("texto", "")).strip()

    if not texto:
        return jsonify({
            "error": "Texto vacío"
        }), 400

    try:
        datos = generar_mp3(texto)

        temporal = tempfile.NamedTemporaryFile(
            delete=False,
            suffix=".mp3"
        )

        temporal.write(datos)
        temporal.close()

        respuesta = send_file(
            temporal.name,
            mimetype="audio/mpeg"
        )

        respuesta.call_on_close(
            lambda: eliminar_archivo_si_existe(
                temporal.name
            )
        )

        return respuesta

    except Exception as e:

        log(f"[BAIFO VOZ] ERROR: {e}")

        return jsonify({
            "error": "No se pudo generar la voz"
        }), 500


# ============================================
# RECIBIR AUDIO DESDE ESP32
# ============================================

@app.route("/audio", methods=["POST"])
def recibir_audio():

    inicio_total = time.monotonic()

    session = request.args.get("session", "")
    final = request.args.get("final", "0")

    # Evitar rutas de archivo peligrosas
    if not re.fullmatch(
        r"[A-Za-z0-9_-]{1,100}",
        session
    ):
        return jsonify({
            "estado": "error",
            "mensaje": "Session invalida"
        }), 400

    audio = request.get_data()

    if not audio:
        return jsonify({
            "estado": "error",
            "mensaje": "No se recibieron datos"
        }), 400

    raw_path = os.path.join(
        UPLOAD_DIR,
        session + ".raw"
    )

    wav_path = os.path.join(
        UPLOAD_DIR,
        session + ".wav"
    )

    # Permite el envio completo del ESP32
    # y los envios antiguos por bloques.
    with open(raw_path, "ab") as f:
        f.write(audio)

    if final != "1":
        return jsonify({
            "estado": "recibiendo",
            "mensaje": "Bloque recibido"
        })

    try:

        with open(raw_path, "rb") as f:
            datos_raw = f.read()

        if len(datos_raw) < 3200:
            return jsonify({
                "estado": "sin_audio",
                "mensaje": "Audio demasiado corto"
            })

        (
            datos_amplificados,
            pico_original,
            pico_final,
            ganancia
        ) = amplificar_pcm16(datos_raw)

        with wave.open(wav_path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(16000)
            wav.writeframes(datos_amplificados)

        log("==============================")
        log("[BAIFO] AUDIO RECIBIDO")
        log(f"Archivo WAV: {wav_path}")
        log(
            f"Bytes WAV: "
            f"{os.path.getsize(wav_path)}"
        )
        log(f"Pico original: {pico_original}")
        log(f"Ganancia: {ganancia:.2f}x")
        log(f"Pico final: {pico_final}")
        log("==============================")

        # ====================================
        # 1. TRANSCRIPCION
        # ====================================

        inicio = time.monotonic()

        with open(wav_path, "rb") as f:

            transcripcion = client.with_options(
                timeout=35.0,
                max_retries=0
            ).audio.transcriptions.create(
                model=TRANSCRIBE_MODEL,
                file=f,
            )

        segundos_whisper = (
            time.monotonic() - inicio
        )

        log(
            f"[BAIFO TIEMPOS] Whisper: "
            f"{segundos_whisper:.2f} s"
        )

        texto_transcrito = (
            transcripcion.text or ""
        ).strip()

        log(
            f"[BAIFO] Texto recibido: "
            f"{texto_transcrito!r}"
        )

        if not texto_transcrito:
            return jsonify({
                "estado": "sin_audio",
                "transcripcion": "",
                "mensaje": "No se detecto ninguna voz"
            })

        pregunta = texto_transcrito

        # ====================================
        # 2. GENERAR RESPUESTA
        # ====================================

        from bot_core import responder_pregunta

        inicio = time.monotonic()

        respuesta = responder_pregunta(pregunta)

        segundos_gpt = (
            time.monotonic() - inicio
        )

        log(
            f"[BAIFO TIEMPOS] GPT: "
            f"{segundos_gpt:.2f} s"
        )

        log(
            f"[BAIFO] Respuesta: "
            f"{respuesta!r}"
        )

        # ====================================
        # 3. GENERAR AUDIO MP3
        # ====================================

        datos_mp3 = generar_mp3(respuesta)

        guardar_mp3(datos_mp3)

        tiempo_total = (
            time.monotonic() - inicio_total
        )

        log(
            f"[BAIFO TIEMPOS] TOTAL: "
            f"{tiempo_total:.2f} s"
        )

        return jsonify({
            "estado": "ok",
            "transcripcion": texto_transcrito,
            "pregunta": pregunta,
            "texto": respuesta,
            "audio": (
                request.host_url.rstrip("/") +
                "/tts/" +
                NOMBRE_ULTIMO_AUDIO
            )
        })

    except Exception as e:

        log("==============================")
        log("[BAIFO] ERROR EN /audio")
        log(
            f"Tipo: "
            f"{type(e).__name__}"
        )
        log(f"Mensaje: {e}")
        log("==============================")

        return jsonify({
            "estado": "error",
            "mensaje": "Error procesando el audio"
        }), 500

    finally:
        eliminar_archivo_si_existe(raw_path)
        eliminar_archivo_si_existe(wav_path)


# ============================================
# SERVIR MP3 AL ESP32
# ============================================

@app.route("/tts/ultima_respuesta.mp3")
def servir_ultima_respuesta():

    if not os.path.isfile(RUTA_ULTIMO_AUDIO):
        return jsonify({
            "estado": "error",
            "mensaje": "Todavia no existe un MP3"
        }), 404

    tamano = os.path.getsize(
        RUTA_ULTIMO_AUDIO
    )

    if tamano <= 0:
        return jsonify({
            "estado": "error",
            "mensaje": "El MP3 esta vacio"
        }), 500

    log(
        f"[BAIFO] Sirviendo MP3: "
        f"{tamano} bytes"
    )

    respuesta = make_response(
        send_file(
            RUTA_ULTIMO_AUDIO,
            mimetype="audio/mpeg",
            conditional=False
        )
    )

    respuesta.headers["Cache-Control"] = (
        "no-store, no-cache, "
        "must-revalidate, max-age=0"
    )

    respuesta.headers["Pragma"] = "no-cache"
    respuesta.headers["Expires"] = "0"

    return respuesta


# ============================================
# INICIAR SERVIDOR
# ============================================

if __name__ == "__main__":

    port = int(
        os.environ.get("PORT", 10000)
    )

    app.run(
        host="0.0.0.0",
        port=port
    )

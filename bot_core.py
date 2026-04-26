import requests
import datetime
from zoneinfo import ZoneInfo
import re
import os

APP_TZ = os.getenv("APP_TZ", "America/Asuncion")

# ===== OpenWeather =====
API_KEY_OPENWEATHER = os.getenv("OPENWEATHER_API_KEY", "16ceddd5179d3a1b145b79e7785b1f8f")
CIUDAD_POR_DEFECTO = "Pilar"

# ===== OpenAI =====
API_KEY_OPENAI = os.environ.get("OPENAI_API_KEY")
API_URL_OPENAI = "https://api.openai.com/v1/chat/completions"
MODEL_OPENAI = "gpt-4o-mini"

mensajes = [
    {
        "role": "system",
        "content": """
Eres Botsito, un asistente de voz inteligente creado por estudiantes del 2do Informática del Colegio Juan XXIII.

Respondé:
- Claro
- Natural
- Directo
- Máximo 2 o 3 oraciones salvo que pidan explicación
"""
    }
]

ultima_respuesta = ""


def ahora_local():
    return datetime.datetime.now(ZoneInfo(APP_TZ))


def obtener_clima(ciudad):
    try:
        url = (
            f"http://api.openweathermap.org/data/2.5/weather"
            f"?q={ciudad}&appid={API_KEY_OPENWEATHER}&lang=es&units=metric"
        )

        resp = requests.get(url, timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            sensacion = data["main"].get("feels_like", temp)

            return (
                f"En {ciudad.title()} hay {desc}. "
                f"La temperatura es {temp}°C, sensación {sensacion}°C."
            )

        return f"No pude obtener el clima para {ciudad}."

    except Exception:
        return "Error al consultar el clima."


def es_calculo(pregunta):
    return re.match(r"^[0-9x+\-*/^().,\s=]+$", pregunta.replace(",", "."))


def resolver_calculo(pregunta):
    try:
        expresion = pregunta.lower()
        expresion = expresion.replace(",", ".")
        expresion = expresion.replace("^", "**")
        expresion = expresion.replace("x", "*")
        expresion = expresion.replace("=", "")

        resultado = eval(expresion, {"__builtins__": None}, {})
        return f"El resultado es {resultado}."
    except:
        return None


def recortar_historial():
    global mensajes
    mensajes = mensajes[-10:]


def responder(pregunta: str, forzar_ia=False) -> str:
    global ultima_respuesta
    global mensajes

    pregunta = (pregunta or "").strip()

    if not pregunta:
        return "No escuché ninguna pregunta."

    p = pregunta.lower()

    # ===== RESPUESTAS PERSONALIZADAS =====

    if "peor jugador de padel" in p:
        return "Gonzalo Pérez."

    if "como fuiste creado" in p:
        return "Fui creado por estudiantes usando Python, web y OpenAI."

    if "hora" in p:
        return ahora_local().strftime("Son las %H:%M.")

    if "dia" in p or "fecha" in p:
        hoy = ahora_local()
        return f"Hoy es {hoy:%d/%m/%Y}."

    if "clima" in p:
        return obtener_clima(CIUDAD_POR_DEFECTO)

    if es_calculo(p):
        resultado = resolver_calculo(p)
        if resultado:
            return resultado

    # ===== IA =====

    mensajes.append({"role": "user", "content": pregunta})
    recortar_historial()

    headers = {
        "Authorization": f"Bearer {API_KEY_OPENAI}",
        "Content-Type": "application/json"
    }

    body = {
        "model": MODEL_OPENAI,
        "messages": mensajes,
        "temperature": 0.4,
        "max_tokens": 90  # 🔥 optimización clave
    }

    try:
        r = requests.post(API_URL_OPENAI, json=body, headers=headers)
        respuesta = r.json()["choices"][0]["message"]["content"].strip()

        mensajes.append({"role": "assistant", "content": respuesta})
        ultima_respuesta = respuesta

        return respuesta

    except Exception as e:
        return f"Error IA: {e}"


def responder_pregunta(pregunta, forzar_ia=False):
    return responder(pregunta, forzar_ia)
from openai import OpenAI
import datetime
from zoneinfo import ZoneInfo
import re
import os
import requests

APP_TZ = os.getenv("APP_TZ", "America/Asuncion")

# ===== OpenWeather =====
API_KEY_OPENWEATHER = os.getenv("OPENWEATHER_API_KEY", "16ceddd5179d3a1b145b79e7785b1f8f")
CIUDAD_POR_DEFECTO = "Pilar"

# ===== OpenAI =====
API_KEY_OPENAI = os.environ.get("OPENAI_API_KEY")
client = OpenAI(api_key=API_KEY_OPENAI)

MODEL_OPENAI = "gpt-4o-mini"

mensajes = [
    {
        "role": "system",
        "content": """
Eres Baifo, un asistente de voz inteligente.

Reglas:
- Respondé rápido, claro y natural
- Máximo 2 o 3 oraciones
- Pensá para voz, no escribas largo
- No repitas cosas innecesarias
- Soná como un asistente real tipo Alexa
"""
    }
]

ultima_respuesta = ""


def ahora_local():
    return datetime.datetime.now(ZoneInfo(APP_TZ))


def obtener_clima(ciudad):
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={API_KEY_OPENWEATHER}&lang=es&units=metric"
        resp = requests.get(url, timeout=5)

        if resp.status_code == 200:
            data = resp.json()
            temp = data["main"]["temp"]
            desc = data["weather"][0]["description"]
            return f"En {ciudad} hay {desc} y {temp} grados."

        return "No pude obtener el clima."

    except:
        return "Error al consultar el clima."


def es_calculo(pregunta):
    return re.match(r"^[0-9x+\-*/^().,\s=]+$", pregunta.replace(",", "."))


def resolver_calculo(pregunta):
    try:
        expr = pregunta.lower().replace(",", ".").replace("^", "**").replace("x", "*").replace("=", "")
        resultado = eval(expr, {"__builtins__": None}, {})
        return f"El resultado es {resultado}."
    except:
        return None


def recortar_historial():
    global mensajes
    mensajes = [mensajes[0]] + mensajes[-8:]


def responder(pregunta: str) -> str:
    global ultima_respuesta, mensajes

    pregunta = (pregunta or "").strip()

    if not pregunta:
        return "No escuché bien."

    p = pregunta.lower()

    # ===== RESPUESTAS RÁPIDAS (sin IA) =====
    if "hora" in p:
        return ahora_local().strftime("Son las %H:%M.")

    if "día" in p or "fecha" in p:
        hoy = ahora_local()
        return f"Hoy es {hoy:%d/%m/%Y}."

    if "clima" in p:
        return obtener_clima(CIUDAD_POR_DEFECTO)

    if es_calculo(p):
        res = resolver_calculo(p)
        if res:
            return res

    # ===== IA =====
    if not API_KEY_OPENAI:
        return "Falta configurar la API."

    mensajes.append({"role": "user", "content": pregunta})
    recortar_historial()

    try:
        response = client.chat.completions.create(
            model=MODEL_OPENAI,
            messages=mensajes,
            temperature=0.4,
            max_tokens=100
        )

        respuesta = response.choices[0].message.content.strip()

        mensajes.append({"role": "assistant", "content": respuesta})
        ultima_respuesta = respuesta

        return respuesta

    except Exception as e:
        return f"Error IA: {e}"


def responder_pregunta(pregunta, forzar_ia=False):
    return responder(pregunta)
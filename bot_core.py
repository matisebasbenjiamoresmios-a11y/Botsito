import requests
import datetime
import re

API_KEY_OPENWEATHER = "16ceddd5179d3a1b145b79e7785b1f8f"
CIUDAD_POR_DEFECTO = "Pilar"
import os
API_KEY_OPENAI = os.environ.get("OPENROUTER_API_KEY")
API_URL_OPENAI = "https://openrouter.ai/api/v1/chat/completions"
MODEL_OPENAI = "mistralai/mistral-7b-instruct:free"

mensajes = [{
    "role": "system",
    "content": "Eres Botsito, un chatbot confiable y servicial. Sabés responder preguntas prácticas y también sabés resumir textos largos en español cuando se te pide. Siempre respondé de manera clara y directa."
}]

ultima_respuesta = ""

def obtener_clima(ciudad):
    url = f"http://api.openweathermap.org/data/2.5/weather?q={ciudad}&appid={API_KEY_OPENWEATHER}&lang=es&units=metric"
    resp = requests.get(url)
    if resp.status_code == 200:
        data = resp.json()
        temp = data['main']['temp']
        desc = data['weather'][0]['description']
        return f"El clima en {ciudad.title()} es {desc} con una temperatura de {temp}°C."
    else:
        return f"No pude obtener el clima para {ciudad}. ¿Seguro que escribiste bien la ciudad?"

def responder(pregunta: str, forzar_ia=False) -> str:
    global ultima_respuesta
    p = pregunta.lower().strip()

    if not forzar_ia:
        if "quien te creo" in p:
            return "Fui creado por un grupo de estudiantes del 2do Informática del Colegio Juan XXIII."
        if "que hora es" in p:
            return datetime.datetime.now().strftime("La hora actual es: %H:%M:%S")
        if "que dia es" in p or "qué día es" in p:
            hoy = datetime.datetime.now()
            dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
            return f"Hoy es {dias[hoy.weekday()]}, {hoy:%d/%m/%Y}."
        if "qué dijiste antes" in p or "qué respondiste" in p or "resumime" in p or "lo anterior" in p:
            return ultima_respuesta if ultima_respuesta else "Todavía no respondí nada."
        if "clima" in p or "tiempo" in p or "temperatura" in p:
            palabras = p.split()
            ciudad = None
            for i, palabra in enumerate(palabras):
                if palabra in ["en", "de"]:
                    if i + 1 < len(palabras):
                        ciudad = palabras[i + 1]
                        break
            if ciudad:
                return obtener_clima(ciudad)
            else:
                return obtener_clima(CIUDAD_POR_DEFECTO)
        try:
            if re.match(r"^[0-9x+\-*/^().\s=]+$", p.replace(",", ".")):
                expresion = p.replace("^", "**").replace("x", "*")
                resultado = eval(expresion)
                return f"El resultado es: {resultado}"
        except:
            pass

    mensajes.append({"role": "user", "content": pregunta})
    headers = {"Authorization": f"Bearer {API_KEY_OPENAI}", "Content-Type": "application/json"}
    body = {"model": MODEL_OPENAI, "messages": mensajes}

    try:
        r = requests.post(API_URL_OPENAI, json=body, headers=headers)
        r.raise_for_status()
        respuesta = r.json()["choices"][0]["message"]["content"]
        mensajes.append({"role": "assistant", "content": respuesta})
        ultima_respuesta = respuesta
        return respuesta
    except Exception as e:
        return f"Error al conectar con OpenAI / OpenRouter: {e}"

def responder_pregunta(pregunta, forzar_ia=False):
    return responder(pregunta, forzar_ia=forzar_ia)


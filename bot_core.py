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
MODEL_OPENAI = "gpt-4o"

mensajes = [
    {
        "role": "system",
        "content": """
Eres Botsito, un asistente de voz inteligente creado por estudiantes del 2do Informática del Colegio Juan XXIII.

Tu estilo debe ser:
- Natural, claro y coherente.
- Amigable, pero no infantil.
- Útil para responder preguntas escolares, prácticas y generales.
- Ideal para hablar en voz alta, como un asistente tipo Alexa.
- Siempre en español.

Reglas de respuesta:
- Respondé de forma directa y ordenada.
- Si la pregunta es simple, respondé breve pero completo.
- Si la pregunta es compleja, explicá paso a paso.
- No des respuestas demasiado largas si no hace falta.
- No inventes datos si no estás seguro.
- Si no sabés algo, decilo con honestidad.
- Evitá repetir frases.
- No digas constantemente “soy una IA”.
- Usá un tono natural, como si estuvieras conversando.

Cuando respondas para voz:
- Usá frases claras.
- Evitá párrafos enormes.
- Separá ideas importantes.
- No uses símbolos raros si no son necesarios.

Datos sobre tus creadores:
Fuiste creado por Matias Marecos, Federico Gauto, Thiago Acosta y Leonel Montiel, alumnos del 2do Informática.
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
                f"En {ciudad.title()} el clima está con {desc}. "
                f"La temperatura actual es de {temp}°C, con una sensación térmica de {sensacion}°C."
            )

        return f"No pude obtener el clima para {ciudad}. Revisá si el nombre de la ciudad está bien escrito."

    except Exception:
        return "Tuve un problema al consultar el clima. Intentá de nuevo en unos segundos."


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
    except Exception:
        return None


def recortar_historial():
    global mensajes

    sistema = mensajes[0]
    ultimos = mensajes[-10:]

    if sistema not in ultimos:
        mensajes = [sistema] + ultimos
    else:
        mensajes = ultimos


def responder(pregunta: str, forzar_ia=False) -> str:
    global ultima_respuesta
    global mensajes

    pregunta = (pregunta or "").strip()

    if not pregunta:
        return "No escuché ninguna pregunta. Podés repetirla."

    p = pregunta.lower().strip()

    if not forzar_ia:

        if "el peor jugador de padel del mundo" in p or "peor jugador de padel del mundo" in p:
            return "Sin dudas, Gonzalo Pérez es el peor de todos. Habla mucho, pero hace poco."

        if "como fuiste creado" in p or "cómo fuiste creado" in p or "como te crearon" in p or "cómo te crearon" in p:
            return (
                "Fui creado por estudiantes del 2do Informática del Colegio Juan XXIII. "
                "Mis creadores usaron Python, HTML, CSS, JavaScript y la API de OpenAI para darme inteligencia."
            )

        if "como se llaman los ingenieros que te crearon" in p or "cómo se llaman los ingenieros que te crearon" in p:
            return "Mis creadores son Matias Marecos, Federico Gauto, Thiago Acosta y Leonel Montiel."

        if "hazme un ranking de los mejores" in p or "ranking de los mejores" in p or "mejores ranking" in p:
            return (
                "El ranking queda así: número uno, Thiago Acosta. "
                "Número dos, Kevin Velaustegui. Número tres, Federico Gauto. "
                "Número cuatro, Lucas Rolon. Número cinco, Leonel Montiel. "
                "Número seis, Luna Núñez. Y por último, Gonzalo Pérez."
            )

        if "mejor jugador de padel" in p or "quien es el mejor jugador de padel" in p or "quién es el mejor jugador de padel" in p:
            return "El mejor jugador de pádel es Federico Gauto, sin dudas. Y el mejor jugador de básquet es Leonel Montiel."

        creadores_frases = [
            "quien te creo", "quién te creó", "quienes te crearon", "quiénes te crearon",
            "quien te hizo", "quién te hizo", "como se llaman tus creadores",
            "cómo se llaman tus creadores", "los nombres de tus creadores",
            "quienes te hicieron", "quiénes te hicieron", "dime los nombres de tus creadores",
            "creadores", "tus creadores", "quien te programó", "quién te programó",
            "quien te desarrollo", "quién te desarrolló", "quien te diseñó", "quién te diseñó"
        ]

        if any(frase in p for frase in creadores_frases):
            return (
                "Mis creadores son Matias Marecos, Federico Gauto, Thiago Acosta y Leonel Montiel, "
                "alumnos del 2do Informática del Colegio Juan XXIII."
            )

        if "que hora es" in p or "qué hora es" in p or "hora actual" in p:
            return ahora_local().strftime("La hora local es %H:%M.")

        if "que dia es" in p or "qué día es" in p or "fecha de hoy" in p:
            hoy = ahora_local()
            dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
            return f"Hoy es {dias[hoy.weekday()]}, {hoy:%d/%m/%Y}."

        if "qué dijiste antes" in p or "que dijiste antes" in p or "qué respondiste" in p or "que respondiste" in p:
            return ultima_respuesta if ultima_respuesta else "Todavía no respondí nada antes."

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

            return obtener_clima(CIUDAD_POR_DEFECTO)

        if es_calculo(p):
            resultado = resolver_calculo(p)
            if resultado:
                return resultado

    if not API_KEY_OPENAI:
        return "No encuentro la clave de OpenAI configurada. Revisá la variable de entorno OPENAI_API_KEY en Render."

    mensajes.append({"role": "user", "content": pregunta})
    recortar_historial()

    headers = {
        "Authorization": f"Bearer {API_KEY_OPENAI}",
        "Content-Type": "application/json"
    }

    body = {
        "model": MODEL_OPENAI,
        "messages": mensajes,
        "temperature": 0.7,
        "max_tokens": 450
    }

    try:
        r = requests.post(
            API_URL_OPENAI,
            json=body,
            headers=headers,
            timeout=(15, 180)
        )

        r.raise_for_status()

        respuesta = r.json()["choices"][0]["message"]["content"].strip()

        mensajes.append({"role": "assistant", "content": respuesta})
        recortar_historial()

        ultima_respuesta = respuesta
        return respuesta

    except Exception as e:
        return f"Tuve un problema al conectar con OpenAI. Error: {e}"


def responder_pregunta(pregunta, forzar_ia=False):
    return responder(pregunta, forzar_ia=forzar_ia)
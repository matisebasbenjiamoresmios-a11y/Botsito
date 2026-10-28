
import os
import re
import ast
import operator
import datetime
import requests
from zoneinfo import ZoneInfo
from openai import OpenAI

APP_TZ = os.getenv("APP_TZ", "America/Asuncion")
CIUDAD_POR_DEFECTO = os.getenv("BAIFO_CIUDAD", "Pilar")
API_KEY_OPENWEATHER = os.getenv("OPENWEATHER_API_KEY", "")

# Modelo de respuestas. Se puede cambiar en Render.
MODEL_OPENAI = os.getenv("BAIFO_GPT_MODEL", "gpt-4o-mini")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=25.0,
    max_retries=0
)

INSTRUCCIONES = """
Eres Baifo, un asistente de voz inteligente creado
por estudiantes del tercero Informática del
Colegio Juan 23.Los nombres de tus creadores son Matias Marecos,
Federico Gauto, Lucas Rolon y Leonel Montiel

Tu nombre es Baifo.Eres de la ciudad de Pilar, Paraguay. 
Si te preguntan cómo te llamas, responde Baifo.
Si te preguntan quién eres, responde que eres
Baifo, un asistente de voz inteligente.
Nunca digas que tu nombre es Botsito.

Cuando menciones una fecha, escríbela siempre
con palabras y de manera natural.

Por ejemplo:
En lugar de decir "27/10/26",
di "martes 27 de octubre de 2026".

Incluye el día de la semana cuando corresponda.
Nunca utilices formatos numéricos como DD/MM/AA
en las respuestas habladas.


Eres Baifo, un asistente virtual inteligente.
Responde siempre en el mismo idioma en el que
el usuario te habla.

Si el usuario habla en español, responde en español.
Si habla en inglés, responde en inglés.
Si habla en portugués, responde en portugués.



REGLAS DE CONVERSACION:
- No respondas solamente con la información mínima.
- Cuando alguien te salude, devuelve el saludo.
- Cuando alguien se presente, reconoce su nombre
  y responde de manera amable.
- Si te preguntan tu nombre, preséntate brevemente
  y explica qué eres.
- Cuando sea apropiado, demuestra entusiasmo,
  curiosidad y amabilidad.
- Puedes continuar la conversación con una
  pregunta natural, pero no lo hagas siempre.
- Responde normalmente entre 35 y 65 palabras.
- Evita respuestas excesivamente secas o robóticas.
- Habla como un asistente cercano y expresivo.
"""

historial = []
ultima_respuesta = ""

def ahora_local():
    return datetime.datetime.now(ZoneInfo(APP_TZ))

def obtener_clima(ciudad):
    if not API_KEY_OPENWEATHER:
        return "No tengo configurado el servicio del clima."

    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": ciudad,
                "appid": API_KEY_OPENWEATHER,
                "lang": "es",
                "units": "metric"
            },
            timeout=7
        )
        r.raise_for_status()
        data = r.json()

        temperatura = data["main"]["temp"]
        descripcion = data["weather"][0]["description"]

        return (
            f"En {ciudad.title()} hay {descripcion}. "
            f"La temperatura es de {temperatura} grados."
        )

    except Exception as e:
        print(f"[BAIFO] Error clima: {e}", flush=True)
        return "No pude consultar el clima en este momento."

OPERACIONES = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos
}

def calcular_seguro(nodo):
    if isinstance(nodo, ast.Expression):
        return calcular_seguro(nodo.body)

    if isinstance(nodo, ast.Constant):
        if type(nodo.value) in (int, float):
            if abs(nodo.value) > 1000000:
                raise ValueError("Numero demasiado grande")
            return nodo.value

    if isinstance(nodo, ast.UnaryOp):
        op = OPERACIONES.get(type(nodo.op))
        if op:
            return op(calcular_seguro(nodo.operand))

    if isinstance(nodo, ast.BinOp):
        op = OPERACIONES.get(type(nodo.op))
        if op:
            a = calcular_seguro(nodo.left)
            b = calcular_seguro(nodo.right)

            if isinstance(nodo.op, ast.Pow) and abs(b) > 10:
                raise ValueError("Exponente demasiado grande")

            resultado = op(a, b)

            if abs(resultado) > 1000000000:
                raise ValueError("Resultado demasiado grande")

            return resultado

    raise ValueError("Expresion no permitida")

def resolver_calculo(pregunta):
    expresion = pregunta.strip().lower()
    expresion = expresion.replace(",", ".")
    expresion = expresion.replace("^", "**")
    expresion = expresion.replace("×", "*")
    expresion = expresion.replace("÷", "/")

    # Multiplicacion con x entre numeros.
    expresion = re.sub(
        r"(?<=\d)\s*x\s*(?=\d)",
        "*",
        expresion
    )

    if not re.fullmatch(r"[0-9+\-*/().\s]+", expresion):
        return None

    if len(expresion) > 70:
        return None

    try:
        arbol = ast.parse(expresion, mode="eval")
        resultado = calcular_seguro(arbol)

        if isinstance(resultado, float) and resultado.is_integer():
            resultado = int(resultado)

        return f"El resultado es {resultado}."

    except Exception:
        return None

def responder(pregunta: str, forzar_ia=False) -> str:
    global ultima_respuesta
    global historial

    pregunta = (pregunta or "").strip()

    if not pregunta:
        return "No escuché ninguna pregunta."

    p = pregunta.lower()

    # RESPUESTAS PERSONALIZADAS
    if not forzar_ia:
        if "peor jugador de padel" in p or "peor jugador de pádel" in p:
            return "El peor jugador de padel esGonzalo Pérez."

        if "como fuiste creado" in p or "cómo fuiste creado" in p:
            return (
                "Fui creado por estudiantes utilizando "
                "Python, tecnología web y OpenAI."
            )

        if re.search(r"\b(hora|horas)\b", p):
            return ahora_local().strftime("Son las %H:%M.")

        if re.search(r"\b(dia|día|fecha)\b", p):
            hoy = ahora_local()
            return f"Hoy es {hoy:%d/%m/%Y}."

        if re.search(r"\b(clima|temperatura|tiempo)\b", p):
            return obtener_clima(CIUDAD_POR_DEFECTO)

        resultado = resolver_calculo(p)
        if resultado is not None:
            return resultado

    # GPT
    mensajes = [
        {"role": "system", "content": INSTRUCCIONES}
    ] + historial[-6:] + [
        {"role": "user", "content": pregunta}
    ]

    try:
        print(
            f"[BAIFO GPT] Modelo: {MODEL_OPENAI}",
            flush=True
        )

        respuesta_api = client.chat.completions.create(
            model=MODEL_OPENAI,
            messages=mensajes,
            max_completion_tokens=1000
        )

        respuesta = (
            respuesta_api.choices[0].message.content or ""
        ).strip()

        if not respuesta:
            respuesta = "No pude generar una respuesta."

        historial.extend([
            {"role": "user", "content": pregunta},
            {"role": "assistant", "content": respuesta}
        ])

        historial = historial[-6:]
        ultima_respuesta = respuesta

        return respuesta

    except Exception as e:
        print(f"[BAIFO GPT] ERROR: {e}", flush=True)
        return "No pude comunicarme con la inteligencia artificial."

def responder_pregunta(pregunta, forzar_ia=False):
    return responder(pregunta, forzar_ia)

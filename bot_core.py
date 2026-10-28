
import os
import re
import ast
import operator
import datetime
import unicodedata
import requests

from zoneinfo import ZoneInfo
from openai import OpenAI


# ==========================================
# BAIFO IA - CONFIGURACION
# ==========================================

APP_TZ = os.getenv("APP_TZ", "America/Asuncion")
CIUDAD_POR_DEFECTO = os.getenv("BAIFO_CIUDAD", "Pilar")
API_KEY_OPENWEATHER = os.getenv("OPENWEATHER_API_KEY", "")

MODEL_OPENAI = os.getenv("BAIFO_GPT_MODEL", "gpt-4o-mini")

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    timeout=25.0,
    max_retries=0
)


# ==========================================
# INSTRUCCIONES DE BAIFO
# ==========================================

INSTRUCCIONES = """
Eres Baifo, un asistente de voz inteligente creado
por estudiantes del tercero Informática del
Colegio Juan 23.

Los nombres de tus creadores son Matias Marecos,
Federico Gauto, Lucas Rolon y Leonel Montiel.

Tu nombre es Baifo.
Eres de la ciudad de Pilar, Paraguay.

Si te preguntan cómo te llamas, responde Baifo.
Si te preguntan quién eres, responde que eres
Baifo, un asistente de voz inteligente.
Nunca digas que tu nombre es Botsito.

Responde siempre en el mismo idioma en el que
el usuario te habla.

Si habla en español, responde en español.
Si habla en inglés, responde en inglés.
Si habla en portugués, responde en portugués.

Cuando menciones fechas, utiliza un formato
natural, como "martes 27 de octubre de 2026".
No utilices fechas numéricas en las respuestas.

Cuando menciones temperaturas, utiliza expresiones
naturales como "16 grados Celsius".

No inventes datos meteorológicos.

REGLAS DE CONVERSACION:
- Cuando alguien te salude, devuelve el saludo.
- Cuando alguien se presente, reconoce su nombre.
- Si te preguntan tu nombre, preséntate brevemente.
- Sé amable, natural y expresivo.
- Responde normalmente entre 35 y 65 palabras.
- Para preguntas sencillas, responde brevemente.
- Evita respuestas excesivamente largas.
- Puedes hacer una pregunta de seguimiento cuando
  sea apropiado, pero no siempre.
"""


historial = []
ultima_respuesta = ""


# ==========================================
# FECHA Y HORA LOCAL
# ==========================================

DIAS = [
    "lunes",
    "martes",
    "miércoles",
    "jueves",
    "viernes",
    "sábado",
    "domingo"
]

MESES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre"
]


def ahora_local():
    return datetime.datetime.now(ZoneInfo(APP_TZ))


def fecha_en_palabras(fecha):
    dia_semana = DIAS[fecha.weekday()]
    mes = MESES[fecha.month - 1]

    return (
        f"{dia_semana} {fecha.day} "
        f"de {mes} de {fecha.year}"
    )


def responder_fecha(tipo="hoy"):
    hoy = ahora_local().date()

    if tipo == "manana":
        fecha = hoy + datetime.timedelta(days=1)
        return f"Mañana será {fecha_en_palabras(fecha)}."

    if tipo == "ayer":
        fecha = hoy - datetime.timedelta(days=1)
        return f"Ayer fue {fecha_en_palabras(fecha)}."

    return f"Hoy es {fecha_en_palabras(hoy)}."


# ==========================================
# NUMEROS EN PALABRAS
# ==========================================

UNIDADES = [
    "cero", "uno", "dos", "tres", "cuatro",
    "cinco", "seis", "siete", "ocho",
    "nueve", "diez", "once", "doce",
    "trece", "catorce", "quince",
    "dieciséis", "diecisiete", "dieciocho",
    "diecinueve", "veinte", "veintiuno",
    "veintidós", "veintitrés", "veinticuatro",
    "veinticinco", "veintiséis",
    "veintisiete", "veintiocho",
    "veintinueve"
]

DECENAS = {
    30: "treinta",
    40: "cuarenta",
    50: "cincuenta",
    60: "sesenta",
    70: "setenta",
    80: "ochenta",
    90: "noventa"
}


def numero_en_palabras(numero):
    numero = int(numero)

    if numero < 0:
        return "menos " + numero_en_palabras(-numero)

    if numero < 30:
        return UNIDADES[numero]

    if numero < 100:
        decena = (numero // 10) * 10
        unidad = numero % 10

        if unidad == 0:
            return DECENAS[decena]

        return (
            DECENAS[decena] +
            " y " +
            UNIDADES[unidad]
        )

    return str(numero)


def numero_antes_de_grados(numero):
    texto = numero_en_palabras(numero)

    if texto.endswith("veintiuno"):
        return texto[:-9] + "veintiún"

    if texto.endswith(" y uno"):
        return texto[:-5] + " y un"

    if texto == "uno":
        return "un"

    return texto


# ==========================================
# HORA NATURAL
# ==========================================

def responder_hora():
    ahora = ahora_local()

    hora = ahora.hour
    minuto = ahora.minute

    if hora == 0:
        hora_texto = "doce"
        periodo = "de la madrugada"

    elif hora < 12:
        hora_texto = numero_en_palabras(hora)
        periodo = "de la mañana"

    elif hora == 12:
        hora_texto = "doce"
        periodo = "del mediodía"

    else:
        hora_texto = numero_en_palabras(hora - 12)
        periodo = "de la tarde" if hora < 19 else "de la noche"

    if minuto == 0:
        if hora in (0, 12):
            return f"Son las {hora_texto} {periodo}."
        if hora in (1, 13):
            return f"Es la una {periodo}."
        return f"Son las {hora_texto} {periodo}."

    if minuto == 30:
        minutos_texto = "y media"
    elif minuto == 15:
        minutos_texto = "y cuarto"
    else:
        minutos_texto = "y " + numero_en_palabras(minuto)

    if hora in (1, 13):
        return f"Es la una {minutos_texto} {periodo}."

    return (
        f"Son las {hora_texto} "
        f"{minutos_texto} {periodo}."
    )


# ==========================================
# NORMALIZAR TEXTO
# ==========================================

def normalizar(texto):
    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto
    )

    texto = "".join(
        c for c in texto
        if unicodedata.category(c) != "Mn"
    )

    return texto


# ==========================================
# OPENWEATHER - CLIMA ACTUAL
# ==========================================

def consultar_openweather(endpoint, parametros):
    if not API_KEY_OPENWEATHER:
        print(
            "[BAIFO CLIMA] Falta OPENWEATHER_API_KEY",
            flush=True
        )
        return None

    try:
        parametros = dict(parametros)

        parametros.update({
            "appid": API_KEY_OPENWEATHER,
            "units": "metric",
            "lang": "es"
        })

        respuesta = requests.get(
            "https://api.openweathermap.org/data/2.5/" + endpoint,
            params=parametros,
            timeout=8
        )

        respuesta.raise_for_status()

        return respuesta.json()

    except Exception as e:
        print(
            f"[BAIFO CLIMA] Error: {e}",
            flush=True
        )
        return None


def temperatura_en_palabras(valor):
    temperatura = round(float(valor))

    return (
        numero_antes_de_grados(temperatura)
        + " grados Celsius"
    )


def obtener_clima(ciudad):
    datos = consultar_openweather(
        "weather",
        {"q": ciudad + ",PY"}
    )

    if datos is None:
        return (
            "No pude consultar el clima "
            "en este momento."
        )

    try:
        temperatura = datos["main"]["temp"]

        return (
            f"Actualmente en {ciudad} hay "
            f"{temperatura_en_palabras(temperatura)}."
        )

    except (KeyError, TypeError, ValueError):
        return (
            "No pude interpretar la información "
            "del clima."
        )


# ==========================================
# OPENWEATHER - CLIMA DE MAÑANA
# ==========================================

def obtener_clima_manana(ciudad):
    datos = consultar_openweather(
        "forecast",
        {"q": ciudad + ",PY"}
    )

    if datos is None:
        return (
            "No pude consultar el pronóstico "
            "de mañana en este momento."
        )

    try:
        pronosticos = datos.get("list", [])

        manana = (
            ahora_local().date()
            + datetime.timedelta(days=1)
        )

        candidatos = []

        for item in pronosticos:
            instante = datetime.datetime.fromtimestamp(
                item["dt"],
                ZoneInfo(APP_TZ)
            )

            if instante.date() == manana:
                candidatos.append(
                    (
                        abs(instante.hour - 12),
                        instante,
                        float(item["main"]["temp"])
                    )
                )

        if not candidatos:
            return (
                "Todavía no tengo un pronóstico "
                "disponible para mañana."
            )

        # Elegir el pronóstico más cercano al mediodía.
        candidatos.sort(key=lambda x: x[0])

        temperatura = candidatos[0][2]

        return (
            f"Mañana en {ciudad} se esperan unos "
            f"{temperatura_en_palabras(temperatura)} "
            f"cerca del mediodía."
        )

    except (KeyError, TypeError, ValueError, OSError) as e:
        print(
            f"[BAIFO CLIMA] Error pronostico: {e}",
            flush=True
        )

        return (
            "No pude interpretar el pronóstico "
            "de mañana."
        )


# ==========================================
# DETECTAR CONSULTAS DE FECHA
# ==========================================

def detectar_fecha(p):
    # Evitar interceptar preguntas generales,
    # por ejemplo: "¿Qué día nació Einstein?"

    pregunta_fecha = any(
        expresion in p
        for expresion in [
            "que dia es hoy",
            "que fecha es hoy",
            "cual es la fecha de hoy",
            "en que dia estamos",
            "que dia estamos",
            "fecha actual",
            "dia de hoy",
            "que dia sera manana",
            "que dia es manana",
            "que fecha sera manana",
            "que fecha es manana",
            "que dia fue ayer",
            "que fecha fue ayer"
        ]
    )

    if not pregunta_fecha:
        return None

    if "manana" in p:
        return responder_fecha("manana")

    if "ayer" in p:
        return responder_fecha("ayer")

    return responder_fecha("hoy")


# ==========================================
# DETECTAR CONSULTAS DE HORA
# ==========================================

def detectar_hora(p):
    expresiones = [
        "que hora es",
        "que hora tienes",
        "que hora tenes",
        "dime la hora",
        "decime la hora",
        "hora actual",
        "hora es ahora"
    ]

    if any(expresion in p for expresion in expresiones):
        return responder_hora()

    return None


# ==========================================
# DETECTAR CONSULTAS DEL CLIMA
# ==========================================

def detectar_clima(p):
    palabras_clima = [
        "clima",
        "temperatura",
        "grados",
        "tiempo meteorologico",
        "pronostico",
        "hara frio",
        "hara calor",
        "hace frio",
        "hace calor"
    ]

    preguntas_tiempo = [
        "como estara el tiempo",
        "como esta el tiempo",
        "que tiempo hara",
        "que tiempo hace"
    ]

    es_clima = (
        any(palabra in p for palabra in palabras_clima)
        or any(frase in p for frase in preguntas_tiempo)
    )

    if not es_clima:
        return None

    es_manana = bool(
        re.search(r"\bmanana\b", p)
    )

    if es_manana:
        return obtener_clima_manana(
            CIUDAD_POR_DEFECTO
        )

    # Consultas de otras fechas las atiende GPT.
    if any(
        palabra in p
        for palabra in [
            "ayer",
            "pasado manana",
            "proxima semana",
            "el lunes",
            "el martes",
            "el miercoles",
            "el jueves",
            "el viernes",
            "el sabado",
            "el domingo"
        ]
    ):
        return None

    return obtener_clima(CIUDAD_POR_DEFECTO)


# ==========================================
# CALCULADORA SEGURA
# ==========================================

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
                raise ValueError(
                    "Número demasiado grande"
                )
            return nodo.value

    if isinstance(nodo, ast.UnaryOp):
        op = OPERACIONES.get(type(nodo.op))

        if op:
            return op(
                calcular_seguro(nodo.operand)
            )

    if isinstance(nodo, ast.BinOp):
        op = OPERACIONES.get(type(nodo.op))

        if op:
            a = calcular_seguro(nodo.left)
            b = calcular_seguro(nodo.right)

            if isinstance(nodo.op, ast.Pow) and abs(b) > 10:
                raise ValueError(
                    "Exponente demasiado grande"
                )

            if isinstance(nodo.op, ast.Div) and b == 0:
                raise ValueError(
                    "División por cero"
                )

            resultado = op(a, b)

            if abs(resultado) > 1000000000:
                raise ValueError(
                    "Resultado demasiado grande"
                )

            return resultado

    raise ValueError("Expresión no permitida")


def resolver_calculo(pregunta):
    expresion = pregunta.strip().lower()

    expresion = expresion.replace(",", ".")
    expresion = expresion.replace("^", "**")
    expresion = expresion.replace("×", "*")
    expresion = expresion.replace("÷", "/")

    expresion = re.sub(
        r"(?<=\d)\s*x\s*(?=\d)",
        "*",
        expresion
    )

    if not re.fullmatch(
        r"[0-9+\-*/().\s]+",
        expresion
    ):
        return None

    if len(expresion) > 70:
        return None

    try:
        arbol = ast.parse(
            expresion,
            mode="eval"
        )

        resultado = calcular_seguro(arbol)

        if (
            isinstance(resultado, float)
            and resultado.is_integer()
        ):
            resultado = int(resultado)

        return f"El resultado es {resultado}."

    except Exception:
        return None


# ==========================================
# RESPUESTAS DE BAIFO
# ==========================================

def responder(pregunta: str, forzar_ia=False):
    global ultima_respuesta
    global historial

    pregunta = (pregunta or "").strip()

    if not pregunta:
        return "No escuché ninguna pregunta."

    p = normalizar(pregunta)

    if not forzar_ia:

        # Respuestas personalizadas existentes.
        if (
            "peor jugador de padel" in p
        ):
            ultima_respuesta = (
                "El peor jugador de padel es Gonzalo Pérez."
            )
            return ultima_respuesta

        if (
            "como fuiste creado" in p
        ):
            ultima_respuesta = (
                "Fui creado por estudiantes utilizando "
                "Python, tecnología web y OpenAI."
            )
            return ultima_respuesta

        # Fecha.
        respuesta_fecha = detectar_fecha(p)

        if respuesta_fecha is not None:
            ultima_respuesta = respuesta_fecha
            return respuesta_fecha

        # Hora.
        respuesta_hora = detectar_hora(p)

        if respuesta_hora is not None:
            ultima_respuesta = respuesta_hora
            return respuesta_hora

        # Clima.
        respuesta_clima = detectar_clima(p)

        if respuesta_clima is not None:
            ultima_respuesta = respuesta_clima
            return respuesta_clima

        # Calculadora.
        resultado = resolver_calculo(pregunta)

        if resultado is not None:
            ultima_respuesta = resultado
            return resultado

    # ======================================
    # RESPUESTAS CON GPT
    # ======================================

    mensajes = [
        {
            "role": "system",
            "content": INSTRUCCIONES
        }
    ] + historial[-6:] + [
        {
            "role": "user",
            "content": pregunta
        }
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
            respuesta = (
                "No pude generar una respuesta."
            )

        historial.extend([
            {
                "role": "user",
                "content": pregunta
            },
            {
                "role": "assistant",
                "content": respuesta
            }
        ])

        historial = historial[-6:]
        ultima_respuesta = respuesta

        return respuesta

    except Exception as e:
        print(
            f"[BAIFO GPT] ERROR: {e}",
            flush=True
        )

        return (
            "No pude comunicarme con "
            "la inteligencia artificial."
        )


# ==========================================
# COMPATIBILIDAD CON APP.PY
# ==========================================

def responder_pregunta(pregunta, forzar_ia=False):
    return responder(pregunta, forzar_ia)

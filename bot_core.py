import datetime
from zoneinfo import ZoneInfo
import os

APP_TZ = os.getenv("APP_TZ", "America/Asuncion")

def ahora_local():
    return datetime.datetime.now(ZoneInfo(APP_TZ))

def responder_pregunta(pregunta):
    if not pregunta:
        return "No escuché bien."

    p = pregunta.lower()

    if "hora" in p:
        return ahora_local().strftime("Son las %H:%M.")

    if "día" in p or "fecha" in p:
        hoy = ahora_local()
        return f"Hoy es {hoy:%d/%m/%Y}."

    return None
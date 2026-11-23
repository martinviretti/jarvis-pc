"""Tests de lo que Jarvis entiende. Corren sin micrófono ni modelos: python -m pytest"""

from datetime import date, datetime, time

import pytest

from jarvis.intents import interpretar
from jarvis.texto import normalizar, parsear_cuando, parsear_duracion, resolver_alarma, resolver_evento

AHORA = datetime(2026, 11, 23, 15, 0)  # lunes 15:00


@pytest.mark.parametrize("frase,intent", [
    ("Hey Jarvis, poné un timer de diez minutos", "timer"),
    ("timer de 5 minutos para los fideos", "timer"),
    ("avisame en media hora", "timer"),
    ("cuánto falta", "cuanto_falta"),
    ("cancelá el timer", "cancelar_timer"),
    ("poné una alarma a las siete", "alarma"),
    ("despertame mañana a las 7 y media", "alarma"),
    ("qué alarmas tengo", "listar_alarmas"),
    ("borrá la alarma", "cancelar_alarma"),
    ("recordame mañana a las cinco llevar la carpeta", "recordatorio"),
    ("agregá dentista al calendario el jueves a las 4", "agregar_evento"),
    ("qué tengo hoy", "que_tengo"),
    ("qué tengo mañana", "que_tengo"),
    ("anotá estudiar matemática", "agregar_tarea"),
    ("agregá comprar cartulina a la lista", "agregar_tarea"),
    ("qué tengo anotado", "listar_tareas"),
    ("tachá estudiar matemática", "completar_tarea"),
    ("prendé la luz", "luz"),
    ("apagá la luz", "luz"),
    ("Tapa la luz", "luz"),
    ("suspendé la PC", "suspender"),
    ("apagá la compu", "apagar_pc"),
    ("cancelá el apagado", "cancelar_apagado"),
    ("subí el volumen", "volumen_cambiar"),
    ("bajá el volumen", "volumen_cambiar"),
    ("volumen al 30", "volumen_poner"),
    ("silencio", "silenciar"),
    ("poné música", "musica_play"),
    ("pausá", "musica_pausa"),
    ("pasá el tema", "musica_siguiente"),
    ("qué tema es este", "que_suena"),
    ("buscá en YouTube cómo hacer slime", "youtube"),
    ("Buscan yo tuve como hacer slime", "youtube"),
    ("abrí ChatGPT", "abrir"),
    ("abrí minecraft", "abrir"),
    ("va a llover mañana", "clima"),
    ("qué hora es", "hora"),
    ("qué día es hoy", "fecha"),
    ("modo juego", "modo_juego"),
    ("desactivá el modo juego", "modo_juego"),
    ("buenas noches", "buenas_noches"),
    ("qué podés hacer", "ayuda"),
    ("sí", "si"),
    ("no", "no"),
    ("gracias", "gracias"),
    ("blablabla cosa rara", "no_entendi"),
])
def test_intents(frase, intent):
    assert interpretar(frase).nombre == intent


def test_datos_de_intents():
    assert interpretar("poné un timer de veinticinco minutos").datos["segundos"] == 1500
    assert interpretar("timer de 10 minutos para los fideos").datos["etiqueta"] == "los fideos"
    assert interpretar("apagá la luz").datos["encender"] is False
    assert interpretar("bajá el volumen").datos["delta"] < 0
    assert interpretar("volumen al treinta").datos["valor"] == 30
    assert interpretar("buscá en YouTube cómo hacer slime").datos["consulta"] == "como hacer slime"
    assert interpretar("abrí el ChatGPT").datos["app"] == "chatgpt"
    assert interpretar("tachá estudiar matemática").datos["texto"] == "estudiar matematica"


def test_normalizar():
    assert normalizar("Hey Jarvis, ¿qué hora es?") == "que hora es"
    assert normalizar("veinticinco minutos") == "25 minutos"
    assert normalizar("treinta y cinco") == "35"
    assert normalizar("un minuto") == "1 minuto"


def test_duraciones():
    assert parsear_duracion("1 hora y media")[0] == 5400
    assert parsear_duracion("media hora")[0] == 1800
    assert parsear_duracion("90 segundos")[0] == 90


def test_alarma_proxima_ocurrencia():
    c = parsear_cuando(normalizar("alarma a las siete"), AHORA)
    assert resolver_alarma(c, AHORA) == datetime(2026, 11, 24, 7, 0)
    c = parsear_cuando(normalizar("alarma a las 9 de la noche"), AHORA)
    assert resolver_alarma(c, AHORA) == datetime(2026, 11, 23, 21, 0)


def test_evento_asume_tarde():
    c = parsear_cuando(normalizar("mañana a las cinco llevar la carpeta"), AHORA)
    inicio, con_hora = resolver_evento(c, AHORA)
    assert con_hora and inicio == datetime(2026, 11, 24, 17, 0)
    assert c.resto == "llevar la carpeta"


def test_evento_dia_semana_y_fecha():
    c = parsear_cuando(normalizar("dentista el jueves a las cuatro y media"), AHORA)
    assert resolver_evento(c, AHORA)[0] == datetime(2026, 11, 26, 16, 30)
    c = parsear_cuando(normalizar("el 30 de noviembre cumple de juli"), AHORA)
    assert c.fecha == date(2026, 11, 30) and c.hora is None
    c = parsear_cuando(normalizar("despertame mañana a las 7 y cuarto de la mañana"), AHORA)
    assert c.hora == time(7, 15)


def test_relativo():
    c = parsear_cuando(normalizar("en 20 minutos sacar la ropa"), AHORA)
    assert resolver_evento(c, AHORA)[0] == datetime(2026, 11, 23, 15, 20)

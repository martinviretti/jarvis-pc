"""Clima con Open-Meteo (gratis, sin cuenta ni clave)."""

from __future__ import annotations

import requests

URL = "https://api.open-meteo.com/v1/forecast"

# Códigos WMO -> texto
_CODIGOS = {
    0: "despejado", 1: "mayormente despejado", 2: "parcialmente nublado", 3: "nublado",
    45: "con niebla", 48: "con niebla",
    51: "con llovizna", 53: "con llovizna", 55: "con llovizna fuerte",
    56: "con llovizna helada", 57: "con llovizna helada",
    61: "con lluvia débil", 63: "con lluvia", 65: "con lluvia fuerte",
    66: "con lluvia helada", 67: "con lluvia helada",
    71: "con nieve", 73: "con nieve", 75: "con nieve fuerte", 77: "con nieve",
    80: "con chaparrones", 81: "con chaparrones", 82: "con chaparrones fuertes",
    85: "con nieve", 86: "con nieve",
    95: "con tormenta", 96: "con tormenta y granizo", 99: "con tormenta y granizo",
}


def _desc(codigo: int | None) -> str:
    return _CODIGOS.get(int(codigo or 0), "variable")


def pronostico(lat: float, lon: float) -> dict:
    r = requests.get(URL, params={
        "latitude": lat, "longitude": lon,
        "current": "temperature_2m,weather_code",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
        "timezone": "auto", "forecast_days": 2,
    }, timeout=8)
    r.raise_for_status()
    return r.json()


def resumen(lat: float, lon: float, ciudad: str, dia: int = 0) -> str:
    """dia=0 hoy, dia=1 mañana."""
    d = pronostico(lat, lon)
    daily = d["daily"]
    maxima = round(daily["temperature_2m_max"][dia])
    minima = round(daily["temperature_2m_min"][dia])
    lluvia = daily["precipitation_probability_max"][dia] or 0
    desc = _desc(daily["weather_code"][dia])
    if dia == 0:
        actual = round(d["current"]["temperature_2m"])
        txt = f"En {ciudad} hace {actual} grados, {_desc(d['current']['weather_code'])}. Máxima de {maxima} y mínima de {minima}."
    else:
        txt = f"Mañana en {ciudad}: {desc}, máxima de {maxima} y mínima de {minima}."
    if lluvia >= 60:
        txt += f" Hay {lluvia} por ciento de probabilidad de lluvia: llevá paraguas."
    elif lluvia >= 30:
        txt += f" Puede llover, {lluvia} por ciento de probabilidad."
    return txt

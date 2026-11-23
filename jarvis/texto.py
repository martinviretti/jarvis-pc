"""Entender texto en español rioplatense: normalizar, números, duraciones, fechas y horas.

Todo es determinístico (sin IA), así se puede probar con tests.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

# ---------------------------------------------------------------- normalizar

_PALABRAS_ACTIVACION = r"^(?:(?:hey|ey|ei|oye|oi|hola|che)\s+)?(?:jarvis|yarvis|jarvi|harvis|llarvis)\b[\s,]*"


def sin_tildes(s: str) -> str:
    # Se quita la tilde de la ñ también: "mañana" y "manana" quedan iguales.
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes ni signos, números en dígitos y sin el "Hey Jarvis" del principio."""
    t = sin_tildes(texto.lower())
    t = re.sub(r"(\d)[:.](\d\d)\b", r"\1:\2", t)  # 17.30 -> 17:30
    t = re.sub(r"[^\w\s:%]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    t = re.sub(_PALABRAS_ACTIVACION, "", t).strip()
    t = palabras_a_numeros(t)
    return t


# ---------------------------------------------------------------- números

_UNIDADES = {
    "cero": 0, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "seis": 6, "siete": 7, "ocho": 8, "nueve": 9,
}
_ESPECIALES = {
    "diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
    "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19,
    "veinte": 20, "veintiuno": 21, "veintiun": 21, "veintiuna": 21, "veintidos": 22,
    "veintitres": 23, "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26,
    "veintisiete": 27, "veintiocho": 28, "veintinueve": 29, "cien": 100,
}
_DECENAS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70, "ochenta": 80, "noventa": 90}
_UNIDADES_TIEMPO = r"(?:segundo|segundos|minuto|minutos|min|hora|horas|dia|dias|semana|semanas)"


def palabras_a_numeros(t: str) -> str:
    """'veinticinco minutos' -> '25 minutos'; 'treinta y cinco' -> '35'; 'a la una' -> 'a la 1'."""
    tokens = t.split()
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in _DECENAS:
            valor = _DECENAS[tok]
            if i + 2 < len(tokens) and tokens[i + 1] == "y" and (tokens[i + 2] in _UNIDADES or tokens[i + 2] in ("uno", "un", "una")):
                valor += _UNIDADES.get(tokens[i + 2], 1)
                i += 2
            out.append(str(valor))
        elif tok in _ESPECIALES:
            out.append(str(_ESPECIALES[tok]))
        elif tok in _UNIDADES:
            out.append(str(_UNIDADES[tok]))
        else:
            out.append(tok)
        i += 1
    t = " ".join(out)
    # "un/una/uno" solo cuando es un número claro.
    t = re.sub(rf"\b(?:un|una|uno)\s+({_UNIDADES_TIEMPO})\b", r"1 \1", t)
    t = re.sub(r"\b(a|de|para)\s+la\s+(?:una|uno)\b", r"\1 la 1", t)
    t = re.sub(r"\b(volumen|al|en)\s+(?:uno|una)\b", r"\1 1", t)
    return t


# ---------------------------------------------------------------- duraciones


def parsear_duracion(t: str) -> tuple[int | None, str]:
    """Busca una duración en texto normalizado. Devuelve (segundos, texto sin la duración)."""
    patrones = [
        (r"\b(\d+) horas? y media\b", lambda m: int(m[1]) * 3600 + 1800),
        (r"\b(\d+) horas? y cuarto\b", lambda m: int(m[1]) * 3600 + 900),
        (r"\b(\d+) horas? y (\d+) (?:minutos?|min)\b", lambda m: int(m[1]) * 3600 + int(m[2]) * 60),
        (r"\b(\d+) (?:minutos?|min) y medio\b", lambda m: int(m[1]) * 60 + 30),
        (r"\b(\d+) (?:minutos?|min) y (\d+) segundos?\b", lambda m: int(m[1]) * 60 + int(m[2])),
        (r"\bmedia hora\b", lambda m: 1800),
        (r"\b(?:1 )?cuarto de hora\b", lambda m: 900),
        (r"\b(\d+) horas?\b", lambda m: int(m[1]) * 3600),
        (r"\b(\d+) (?:minutos?|min)\b", lambda m: int(m[1]) * 60),
        (r"\b(\d+) segundos?\b", lambda m: int(m[1])),
    ]
    for patron, calc in patrones:
        m = re.search(patron, t)
        if m:
            resto = (t[: m.start()] + " " + t[m.end():]).strip()
            return calc(m), re.sub(r"\s+", " ", resto)
    return None, t


def decir_duracion(segundos: int) -> str:
    h, resto = divmod(int(segundos), 3600)
    m, s = divmod(resto, 60)
    partes = []
    if h:
        partes.append("una hora" if h == 1 else f"{h} horas")
    if m:
        partes.append("un minuto" if m == 1 else f"{m} minutos")
    if s and not h:
        partes.append("un segundo" if s == 1 else f"{s} segundos")
    if not partes:
        return "cero segundos"
    return " y ".join(partes) if len(partes) <= 2 else ", ".join(partes[:-1]) + " y " + partes[-1]


# ---------------------------------------------------------------- fechas y horas

DIAS_SEMANA = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DIAS_SEMANA_TILDE = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]


@dataclass
class Cuando:
    fecha: date | None = None      # día pedido (None si no se dijo)
    hora: time | None = None       # hora pedida (None si no se dijo)
    relativo: timedelta | None = None  # "en 20 minutos"
    resto: str = ""                # texto sin la parte de fecha/hora
    periodo_explicito: bool = False  # se dijo mañana/tarde/noche o la hora ya es de 24 h

    @property
    def vacio(self) -> bool:
        return self.fecha is None and self.hora is None and self.relativo is None


def _quitar(t: str, m: re.Match) -> str:
    return re.sub(r"\s+", " ", (t[: m.start()] + " " + t[m.end():])).strip()


def parsear_cuando(t: str, ahora: datetime) -> Cuando:
    """Extrae fecha y hora de texto normalizado. No decide AM/PM: eso lo hace resolver_*."""
    c = Cuando(resto=t)
    texto = t
    periodo: str | None = None

    # relativo: "en 20 minutos", "dentro de 1 hora"
    m = re.search(r"\b(?:en|dentro de)\s+((?:\d+|media|1 cuarto de|cuarto de)\s+[a-z0-9 ]*?(?:horas?|minutos?|min|segundos?)(?: y (?:media|cuarto|medio|\d+ (?:minutos?|segundos?)))?)\b", texto)
    if m:
        seg, _ = parsear_duracion(m[1])
        if seg:
            c.relativo = timedelta(seconds=seg)
            texto = _quitar(texto, m)

    # período del día
    for patron, valor in [
        (r"\b(?:de|a) la madrugada\b", "am"),
        (r"\b(?:de|a) la manana\b", "am"),
        (r"\bpor la manana\b", "am"),
        (r"\b(?:de|a) la tarde\b|\bpor la tarde\b|\besta tarde\b", "pm"),
        (r"\b(?:de|a) la noche\b|\bpor la noche\b|\besta noche\b", "noche"),
    ]:
        m = re.search(patron, texto)
        if m:
            periodo = valor
            if m[0].startswith("esta"):
                c.fecha = ahora.date()
            texto = _quitar(texto, m)
            break

    # día
    m = re.search(r"\bpasado manana\b", texto)
    if m:
        c.fecha = ahora.date() + timedelta(days=2)
        texto = _quitar(texto, m)
    else:
        m = re.search(r"\bmanana\b", texto)
        if m:
            c.fecha = ahora.date() + timedelta(days=1)
            texto = _quitar(texto, m)
        else:
            m = re.search(r"\bhoy\b", texto)
            if m:
                c.fecha = ahora.date()
                texto = _quitar(texto, m)
    if c.fecha is None:
        m = re.search(r"\b(?:el\s+)?(?:proximo\s+|este\s+)?(" + "|".join(DIAS_SEMANA) + r")(?:\s+que viene)?\b", texto)
        if m:
            objetivo = DIAS_SEMANA.index(m[1])
            dias = (objetivo - ahora.weekday()) % 7
            if dias == 0:
                dias = 7
            c.fecha = ahora.date() + timedelta(days=dias)
            texto = _quitar(texto, m)
    if c.fecha is None:
        m = re.search(r"\bel (?:dia )?(\d{1,2})(?: de (" + "|".join(MESES) + r"))?\b(?! (?:minutos?|horas?|segundos?))", texto)
        if m and 1 <= int(m[1]) <= 31:
            dia = int(m[1])
            mes = MESES.index(m[2]) + 1 if m[2] else ahora.month
            anio = ahora.year
            try:
                f = date(anio, mes, dia)
                if f < ahora.date():
                    if m[2]:
                        f = date(anio + 1, mes, dia)
                    else:
                        mes2, anio2 = (mes % 12) + 1, anio + (1 if mes == 12 else 0)
                        f = date(anio2, mes2, dia)
                c.fecha = f
                texto = _quitar(texto, m)
            except ValueError:
                pass

    # hora
    m = re.search(r"\bal mediodia\b|\ba (?:las )?12 del mediodia\b", texto)
    if m:
        c.hora = time(12, 0)
        texto = _quitar(texto, m)
    else:
        m = re.search(r"\ba (?:la )?medianoche\b", texto)
        if m:
            c.hora = time(0, 0)
            periodo = "fijo"
            texto = _quitar(texto, m)
    if c.hora is None:
        m = re.search(
            r"\b(?:a|para|desde) (?:las|la) (\d{1,2})(?::(\d{2})| y (media|cuarto|\d{1,2})| menos (cuarto|\d{1,2}))?(?: (?:en punto|hs|horas))?\b",
            texto,
        )
        if m is None:
            m = re.search(r"\b(?:a las|las) (\d{1,2}):(\d{2})()()\b", texto)
        if m:
            h = int(m[1])
            mi = 0
            if m[2]:
                mi = int(m[2])
            elif m[3]:
                mi = {"media": 30, "cuarto": 15}.get(m[3], None)
                if mi is None:
                    mi = int(m[3])
            elif m[4]:
                resta = 15 if m[4] == "cuarto" else int(m[4])
                h, mi = (h - 1) % 24, 60 - resta
            if 0 <= h <= 23 and 0 <= mi <= 59:
                if periodo in ("pm", "noche") and h < 12:
                    if not (periodo == "noche" and h == 12):
                        h += 12
                elif periodo == "am" and h == 12:
                    h = 0
                c.hora = time(h, mi)
                c.periodo_explicito = periodo is not None or h >= 13 or h == 0
                texto = _quitar(texto, m)

    c.resto = texto
    return c


def resolver_alarma(c: Cuando, ahora: datetime) -> datetime | None:
    """Alarma: 'a las 7' es la próxima vez que sean las 7 (mañana a las 7 si ya pasó)."""
    if c.relativo:
        return ahora + c.relativo
    if c.hora is None:
        return None
    dia = c.fecha or ahora.date()
    dt = datetime.combine(dia, c.hora)
    if c.fecha is None and dt <= ahora:
        dt += timedelta(days=1)
    return dt


def resolver_evento(c: Cuando, ahora: datetime) -> tuple[datetime | date | None, bool]:
    """Evento o recordatorio: devuelve (inicio, tiene_hora).

    'a las 5' sin decir mañana/tarde se toma como 17 h (de 1 a 7 se asume tarde),
    porque un chico casi nunca agenda algo a las 5 de la mañana.
    """
    if c.relativo:
        return ahora + c.relativo, True
    if c.hora is None:
        return (c.fecha, False) if c.fecha else (None, False)
    h = c.hora
    if not c.periodo_explicito and 1 <= h.hour <= 7:
        h = time(h.hour + 12, h.minute)
    dia = c.fecha or ahora.date()
    dt = datetime.combine(dia, h)
    if c.fecha is None and dt <= ahora:
        dt += timedelta(days=1)
    return dt, True


def decir_hora(t: time | datetime) -> str:
    h, m = t.hour, t.minute
    if m == 0:
        return f"{h} en punto" if h not in (0, 12) else ("medianoche" if h == 0 else "12 del mediodía")
    if m == 30:
        return f"{h} y media"
    if m == 15:
        return f"{h} y cuarto"
    return f"{h}:{m:02d}"


def decir_dia(d: date, hoy: date) -> str:
    diff = (d - hoy).days
    if diff == 0:
        return "hoy"
    if diff == 1:
        return "mañana"
    if diff == 2:
        return "pasado mañana"
    nombre = DIAS_SEMANA_TILDE[d.weekday()]
    if 2 < diff < 7:
        return f"el {nombre}"
    return f"el {nombre} {d.day} de {MESES[d.month - 1]}"


def decir_cuando(dt: datetime | date, tiene_hora: bool, ahora: datetime) -> str:
    if isinstance(dt, datetime):
        dia = decir_dia(dt.date(), ahora.date())
        if tiene_hora:
            return f"{dia} a las {decir_hora(dt)}"
        return dia
    return decir_dia(dt, ahora.date())


def limpiar_titulo(t: str) -> str:
    """Saca muletillas del principio y del final para usar el texto como título."""
    t = re.sub(r"^(?:que|de|a|para|el|la|los|las|un|una|y)\s+", "", t.strip())
    t = re.sub(r"\s+(?:por favor|porfa|gracias)$", "", t)
    t = re.sub(r"^(?:que|de|a|para)\s+", "", t)
    return t.strip()

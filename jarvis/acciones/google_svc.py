"""Google Calendar y Google Tasks de la cuenta de tu hijo (se sincronizan con su Android)."""

from __future__ import annotations

import difflib
import logging
from datetime import date, datetime, time, timedelta

from ..config import GOOGLE_CRED_PATH, GOOGLE_TOKEN_PATH

log = logging.getLogger("jarvis")

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/tasks",
]


class GoogleNoConfigurado(Exception):
    pass


def _credenciales():
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    if not GOOGLE_TOKEN_PATH.exists():
        raise GoogleNoConfigurado
    cred = Credentials.from_authorized_user_file(str(GOOGLE_TOKEN_PATH), SCOPES)
    if not cred.valid:
        if cred.expired and cred.refresh_token:
            cred.refresh(Request())
            GOOGLE_TOKEN_PATH.write_text(cred.to_json(), encoding="utf-8")
        else:
            raise GoogleNoConfigurado
    return cred


def iniciar_sesion() -> None:
    """Abre el navegador para que tu hijo autorice a Jarvis (se hace una sola vez)."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not GOOGLE_CRED_PATH.exists():
        raise FileNotFoundError(
            f"Falta {GOOGLE_CRED_PATH}. Seguí la sección 'Conectar Google' del README para descargarlo."
        )
    flujo = InstalledAppFlow.from_client_secrets_file(str(GOOGLE_CRED_PATH), SCOPES)
    cred = flujo.run_local_server(port=0, prompt="consent",
                                  success_message="Listo, Jarvis quedó conectado a Google. Podés cerrar esta pestaña.")
    GOOGLE_TOKEN_PATH.write_text(cred.to_json(), encoding="utf-8")


def _calendar():
    from googleapiclient.discovery import build

    return build("calendar", "v3", credentials=_credenciales(), cache_discovery=False)


def _tasks():
    from googleapiclient.discovery import build

    return build("tasks", "v1", credentials=_credenciales(), cache_discovery=False)


def _zona() -> str:
    try:
        cal = _calendar().settings().get(setting="timezone").execute()
        return cal.get("value", "America/Argentina/Buenos_Aires")
    except Exception:  # noqa: BLE001
        return "America/Argentina/Buenos_Aires"


# ---------------------------------------------------------------- calendario

def crear_evento(titulo: str, inicio: datetime | date, tiene_hora: bool, calendario: str = "primary",
                 aviso_minutos: int = 30, duracion_min: int = 60) -> None:
    if tiene_hora and isinstance(inicio, datetime):
        zona = _zona()
        cuerpo = {
            "summary": titulo,
            "start": {"dateTime": inicio.isoformat(timespec="seconds"), "timeZone": zona},
            "end": {"dateTime": (inicio + timedelta(minutes=duracion_min)).isoformat(timespec="seconds"), "timeZone": zona},
            "reminders": {"useDefault": False, "overrides": [{"method": "popup", "minutes": int(aviso_minutos)}]},
        }
    else:
        d = inicio.date() if isinstance(inicio, datetime) else inicio
        cuerpo = {
            "summary": titulo,
            "start": {"date": d.isoformat()},
            "end": {"date": (d + timedelta(days=1)).isoformat()},
        }
    _calendar().events().insert(calendarId=calendario, body=cuerpo).execute()


def eventos_del_dia(dia: date, calendario: str = "primary") -> list[tuple[str, datetime | None]]:
    """[(título, hora o None si es de todo el día)] ordenados."""
    zona_local = datetime.now().astimezone().tzinfo
    desde = datetime.combine(dia, time.min).replace(tzinfo=zona_local)
    hasta = desde + timedelta(days=1)
    res = _calendar().events().list(
        calendarId=calendario, timeMin=desde.isoformat(), timeMax=hasta.isoformat(),
        singleEvents=True, orderBy="startTime", maxResults=20,
    ).execute()
    salida = []
    for ev in res.get("items", []):
        titulo = ev.get("summary", "(sin título)")
        inicio = ev.get("start", {})
        if "dateTime" in inicio:
            salida.append((titulo, datetime.fromisoformat(inicio["dateTime"]).astimezone(zona_local).replace(tzinfo=None)))
        else:
            salida.append((titulo, None))
    return salida


# ---------------------------------------------------------------- tareas

def crear_tarea(titulo: str, vence: date | None = None) -> None:
    cuerpo: dict = {"title": titulo}
    if vence is not None:
        # Google Tasks guarda solo la fecha (ignora la hora).
        cuerpo["due"] = datetime.combine(vence, time.min).isoformat() + "Z"
    _tasks().tasks().insert(tasklist="@default", body=cuerpo).execute()


def listar_tareas(maximo: int = 15) -> list[tuple[str, date | None]]:
    res = _tasks().tasks().list(tasklist="@default", showCompleted=False, maxResults=maximo).execute()
    salida = []
    for t in res.get("items", []):
        due = t.get("due")
        salida.append((t.get("title", "").strip(), date.fromisoformat(due[:10]) if due else None))
    return [s for s in salida if s[0]]


def completar_tarea(texto: str) -> str | None:
    """Marca como hecha la tarea más parecida a `texto`. Devuelve el título o None."""
    servicio = _tasks()
    res = servicio.tasks().list(tasklist="@default", showCompleted=False, maxResults=50).execute()
    items = [t for t in res.get("items", []) if t.get("title")]
    if not items:
        return None
    titulos = [t["title"].lower() for t in items]
    texto = texto.lower().strip()
    elegido = None
    for i, t in enumerate(titulos):
        if texto and (texto in t or t in texto):
            elegido = i
            break
    if elegido is None:
        parecido = difflib.get_close_matches(texto, titulos, n=1, cutoff=0.5)
        if parecido:
            elegido = titulos.index(parecido[0])
    if elegido is None:
        return None
    tarea = items[elegido]
    servicio.tasks().patch(tasklist="@default", task=tarea["id"], body={"status": "completed"}).execute()
    return tarea["title"]

"""Acciones en la PC: apagar, suspender, bloquear, volumen, música, YouTube y abrir apps."""

from __future__ import annotations

import ctypes
import difflib
import logging
import os
import subprocess
import time
import urllib.parse
import webbrowser

log = logging.getLogger("jarvis")

# Teclas virtuales de Windows
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT = 0xB0
VK_MEDIA_PREV = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
KEYEVENTF_KEYUP = 0x0002

CREATE_NO_WINDOW = 0x08000000


def _tecla(vk: int) -> None:
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


# ---------------------------------------------------------------- energía

def suspender() -> None:
    # Si la hibernación está activada en Windows, esta llamada hiberna en vez de suspender.
    ctypes.windll.powrprof.SetSuspendState(False, True, False)


def apagar(segundos: int = 60) -> None:
    subprocess.run(["shutdown", "/s", "/t", str(segundos), "/c", "Jarvis: la PC se apaga en un minuto."],
                   creationflags=CREATE_NO_WINDOW, check=False)


def cancelar_apagado() -> bool:
    r = subprocess.run(["shutdown", "/a"], creationflags=CREATE_NO_WINDOW, check=False, capture_output=True)
    return r.returncode == 0


def bloquear() -> None:
    ctypes.windll.user32.LockWorkStation()


# ---------------------------------------------------------------- volumen

def _endpoint():
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


def volumen_actual() -> int:
    try:
        return round(_endpoint().GetMasterVolumeLevelScalar() * 100)
    except Exception:  # noqa: BLE001
        return -1


def volumen_poner(porcentaje: int) -> int:
    p = max(0, min(100, int(porcentaje)))
    try:
        ev = _endpoint()
        ev.SetMute(0, None)
        ev.SetMasterVolumeLevelScalar(p / 100.0, None)
    except Exception as e:  # noqa: BLE001
        log.warning("pycaw falló (%s); uso teclas de volumen", e)
        for _ in range(50):
            _tecla(VK_VOLUME_DOWN)
        for _ in range(p // 2):
            _tecla(VK_VOLUME_UP)
    return p


def volumen_cambiar(delta: int) -> int:
    actual = volumen_actual()
    if actual < 0:
        vk = VK_VOLUME_UP if delta > 0 else VK_VOLUME_DOWN
        for _ in range(abs(delta) // 2):
            _tecla(vk)
        return -1
    return volumen_poner(actual + delta)


def silenciar(valor: bool | None = None) -> bool:
    """Silencia (True), quita el silencio (False) o alterna (None). Devuelve si quedó silenciado."""
    try:
        ev = _endpoint()
        nuevo = (not bool(ev.GetMute())) if valor is None else valor
        ev.SetMute(1 if nuevo else 0, None)
        return nuevo
    except Exception:  # noqa: BLE001
        _tecla(VK_VOLUME_MUTE)
        return bool(valor) if valor is not None else True


# ---------------------------------------------------------------- música (Spotify u otro reproductor)

def _sesion_medios():
    """Sesión de medios de Windows (Spotify, navegador, etc.), si la librería está disponible."""
    try:
        import asyncio

        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager as Gestor,
        )

        async def _obtener():
            gestor = await Gestor.request_async()
            return gestor.get_current_session()

        return asyncio.run(_obtener())
    except Exception as e:  # noqa: BLE001
        log.debug("Sin control de medios de Windows: %s", e)
        return None


def _estado_reproduciendo(sesion) -> bool | None:
    try:
        info = sesion.get_playback_info()
        return int(info.playback_status) == 4  # 4 = Playing
    except Exception:  # noqa: BLE001
        return None


def spotify_abierto() -> bool:
    import psutil

    return any((p.info.get("name") or "").lower() == "spotify.exe" for p in psutil.process_iter(["name"]))


def musica_play() -> str:
    sesion = _sesion_medios()
    if sesion is not None and _estado_reproduciendo(sesion):
        return "Ya está sonando."
    if not spotify_abierto() and sesion is None:
        try:
            os.startfile("spotify:")  # noqa: S606
        except OSError:
            return "No encontré Spotify instalado."
        time.sleep(5)
    _tecla(VK_MEDIA_PLAY_PAUSE)
    return "Dale, música."


def musica_pausa() -> str:
    sesion = _sesion_medios()
    if sesion is not None and _estado_reproduciendo(sesion) is False:
        return "Ya está en pausa."
    _tecla(VK_MEDIA_PLAY_PAUSE)
    return "Pausado."


def musica_siguiente() -> None:
    _tecla(VK_MEDIA_NEXT)


def musica_anterior() -> None:
    _tecla(VK_MEDIA_PREV)
    time.sleep(0.15)
    _tecla(VK_MEDIA_PREV)  # el primero vuelve al principio del tema


def que_suena() -> str | None:
    sesion = _sesion_medios()
    if sesion is None:
        return None
    try:
        import asyncio

        props = asyncio.run(_props(sesion))
        if props and props.title:
            artista = f" de {props.artist}" if props.artist else ""
            return f"Está sonando {props.title}{artista}."
    except Exception:  # noqa: BLE001
        return None
    return None


async def _props(sesion):
    return await sesion.try_get_media_properties_async()


# ---------------------------------------------------------------- web y apps

def buscar_youtube(consulta: str) -> None:
    webbrowser.open("https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(consulta))


def buscar_app(nombre: str, apps: dict[str, str]) -> tuple[str, str] | None:
    """Busca la app más parecida en la lista de la config (tolera errores de transcripción)."""
    if not apps:
        return None
    nombre = nombre.strip().lower()
    claves = {k.lower(): (k, v) for k, v in apps.items()}
    if nombre in claves:
        return claves[nombre]
    for k, kv in claves.items():
        if k in nombre or nombre in k:
            return kv
    parecida = difflib.get_close_matches(nombre, list(claves), n=1, cutoff=0.6)
    if parecida:
        return claves[parecida[0]]
    return None


def abrir(destino: str) -> None:
    destino = os.path.expandvars(destino)
    if destino.startswith(("http://", "https://")):
        webbrowser.open(destino)
    else:
        os.startfile(destino)  # noqa: S606 - .exe, .lnk, steam://, spotify:, discord://

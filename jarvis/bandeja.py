"""Ícono de Jarvis en la bandeja de Windows (al lado del reloj)."""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Callable

import pystray
from PIL import Image, ImageDraw

from . import config

log = logging.getLogger("jarvis")

COLORES = {
    "cargando": (140, 140, 150),
    "esperando": (40, 170, 220),
    "escuchando": (60, 200, 120),
    "pensando": (235, 170, 40),
    "silenciado": (210, 70, 60),
    "juego": (150, 110, 220),
}


def _icono(estado: str) -> Image.Image:
    color = COLORES.get(estado, COLORES["esperando"])
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=(20, 24, 34, 255))
    d.ellipse((14, 14, 50, 50), fill=color + (255,))
    d.ellipse((24, 24, 40, 40), fill=(20, 24, 34, 255))
    return img


class Bandeja:
    def __init__(self, al_silenciar: Callable[[bool], None], al_modo_juego: Callable[[bool], None],
                 al_probar: Callable[[], None], al_salir: Callable[[], None]):
        self._silenciado = False
        self._juego = False
        self._estado = "cargando"
        self.al_silenciar = al_silenciar
        self.al_modo_juego = al_modo_juego
        self.al_probar = al_probar
        self.al_salir = al_salir
        menu = pystray.Menu(
            pystray.MenuItem(lambda _i: f"Jarvis: {self._estado}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Silenciar Jarvis", self._toggle_silencio, checked=lambda _i: self._silenciado),
            pystray.MenuItem("Modo juego (solo tecla)", self._toggle_juego, checked=lambda _i: self._juego),
            pystray.MenuItem("Probar la voz", lambda _i, _m: self.al_probar()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Configuración", lambda _i, _m: _abrir_archivo(config.CONFIG_PATH)),
            pystray.MenuItem("Ver historial", lambda _i, _m: _abrir_archivo(config.HISTORIAL_PATH)),
            pystray.MenuItem("Conectar Google", lambda _i, _m: _correr_configurar("--google")),
            pystray.MenuItem("Buscar actualización", lambda _i, _m: _actualizar()),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", self._salir),
        )
        self.icono = pystray.Icon("jarvis", _icono("cargando"), "Jarvis", menu)

    # --- estado
    def estado(self, nombre: str) -> None:
        if self._silenciado and nombre in ("esperando",):
            nombre = "silenciado"
        elif self._juego and nombre == "esperando":
            nombre = "juego"
        self._estado = nombre
        try:
            self.icono.icon = _icono(nombre)
            self.icono.title = f"Jarvis: {nombre}"
            self.icono.update_menu()
        except Exception:  # noqa: BLE001
            pass

    def notificar(self, texto: str) -> None:
        try:
            self.icono.notify(texto[:250], "Jarvis")
        except Exception:  # noqa: BLE001
            pass

    def set_juego(self, valor: bool) -> None:
        self._juego = valor
        self.estado("esperando")

    # --- menú
    def _toggle_silencio(self, _i, _m) -> None:
        self._silenciado = not self._silenciado
        self.al_silenciar(self._silenciado)
        self.estado("esperando")

    def _toggle_juego(self, _i, _m) -> None:
        self.al_modo_juego(not self._juego)

    def _salir(self, _i, _m) -> None:
        self.al_salir()
        self.icono.stop()

    def correr(self, al_listo: Callable[[], None]) -> None:
        def _setup(icono):
            icono.visible = True
            al_listo()
        self.icono.run(setup=_setup)


def _abrir_archivo(ruta) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    if not ruta.exists():
        ruta.write_text("", encoding="utf-8")
    subprocess.Popen(["notepad.exe", str(ruta)])  # noqa: S603, S607


def _python_consola() -> str:
    import sys

    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        exe = exe[:-5] + ".exe"
    return exe


def _correr_configurar(*args: str) -> None:
    subprocess.Popen(["cmd.exe", "/c", "start", "Jarvis - configurar", _python_consola(), "-m", "jarvis.configurar", *args])  # noqa: S603, S607


def _actualizar() -> None:
    script = config.BASE / "instalar.ps1"
    if not script.exists():
        log.error("No encontré %s", script)
        return
    subprocess.Popen(["cmd.exe", "/c", "start", "Jarvis - actualizar", "powershell.exe", "-NoProfile",  # noqa: S603, S607
                      "-ExecutionPolicy", "Bypass", "-File", str(script), "-Actualizar"],
                     cwd=os.environ.get("USERPROFILE"))

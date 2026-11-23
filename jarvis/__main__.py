"""Arranque de Jarvis: carga modelos, abre el micrófono y queda en la bandeja."""

from __future__ import annotations

import ctypes
import logging
import queue
import sys
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler

from . import audio, config
from .acciones.tiempo import Aviso
from .bandeja import Bandeja
from .escucha import Escucha
from .nucleo import Nucleo, Respuesta, frase_aviso

log = logging.getLogger("jarvis")


def _configurar_log() -> None:
    config.asegurar_carpetas()
    h = RotatingFileHandler(config.LOG_PATH, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(threadName)s: %(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)
    if sys.stderr is not None and not sys.executable.lower().endswith("pythonw.exe"):
        log.addHandler(logging.StreamHandler())


def _una_sola_instancia() -> bool:
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW(None, False, "Local\\JarvisPC-una-instancia")
    return ctypes.get_last_error() != 183  # ERROR_ALREADY_EXISTS


def _tecla_desde_texto(nombre: str):
    """'f9' -> Key.f9; 'mouse_x1' -> Button.x1."""
    from pynput import keyboard, mouse

    nombre = (nombre or "f9").strip().lower()
    if nombre.startswith("mouse_"):
        return "mouse", getattr(mouse.Button, nombre.removeprefix("mouse_"), mouse.Button.x1)
    if hasattr(keyboard.Key, nombre):
        return "teclado", getattr(keyboard.Key, nombre)
    if len(nombre) == 1:
        return "teclado", keyboard.KeyCode.from_char(nombre)
    return "teclado", keyboard.Key.f9


class App:
    def __init__(self) -> None:
        self.cfg = config.cargar()
        audio.volumen = float(self.cfg.get("volumen_respuestas", 0.9))
        self.trabajo: queue.Queue = queue.Queue()
        self.bandeja = Bandeja(self._silenciar, self.modo_juego, self._probar_voz, self.salir)
        self.oido = self.boca = self.escucha = None
        self.nucleo = Nucleo(self.cfg, self._sonar_aviso, self.bandeja.notificar, self.modo_juego)
        self._oyentes = []

    # ------------------------------------------------------------------ arranque
    def iniciar(self) -> None:
        threading.Thread(target=self._cargar, name="carga", daemon=True).start()
        self.bandeja.correr(lambda: None)

    def _cargar(self) -> None:
        log.info("Cargando modelos...")
        from .voz import Boca, DetectorHeyJarvis, Oido, modelos_presentes

        try:
            faltan = modelos_presentes(self.cfg["voz"])
            if faltan:
                self.bandeja.estado("silenciado")
                self.bandeja.notificar("Faltan modelos: " + ", ".join(faltan) + ". Corré el instalador de nuevo.")
                log.error("Faltan modelos: %s", faltan)
                return
            self.boca = Boca(self.cfg["voz"], float(self.cfg.get("velocidad_voz", 1.0)))
            self.oido = Oido()
            detector = None
            if self.cfg.get("hey_jarvis", True):
                detector = DetectorHeyJarvis(float(self.cfg.get("sensibilidad_hey_jarvis", 0.5)))
            mic = audio.Microfono(self.cfg.get("microfono"))
            self.escucha = Escucha(mic, detector, self._activado, self._pedido)
            self.escucha.hey_jarvis_activo = detector is not None and not self.cfg.get("modo_juego", False)
            self.bandeja.set_juego(bool(self.cfg.get("modo_juego", False)))
            self.escucha.iniciar()
            self._escuchar_tecla()
            self.nucleo.agenda.iniciar()
            threading.Thread(target=self._trabajar, name="trabajo", daemon=True).start()
            self.bandeja.estado("esperando")
            tecla = self.cfg.get("tecla_hablar", "f9").upper()
            self.bandeja.notificar(f"Jarvis listo. Decí 'Hey Jarvis' o mantené {tecla} para hablar. Micrófono: {mic.nombre}")
            log.info("Jarvis listo.")
        except Exception as e:  # noqa: BLE001
            log.exception("No pude arrancar")
            self.bandeja.estado("silenciado")
            self.bandeja.notificar(f"Jarvis no pudo arrancar: {e}")

    def _escuchar_tecla(self) -> None:
        from pynput import keyboard, mouse

        tipo, objetivo = _tecla_desde_texto(self.cfg.get("tecla_hablar", "f9"))
        if tipo == "mouse":
            def al_click(_x, _y, boton, apretado):
                if boton == objetivo:
                    (self.escucha.tecla_apretada if apretado else self.escucha.tecla_soltada)()
            oyente = mouse.Listener(on_click=al_click)
        else:
            def al_apretar(k):
                if k == objetivo:
                    self.escucha.tecla_apretada()

            def al_soltar(k):
                if k == objetivo:
                    self.escucha.tecla_soltada()
            oyente = keyboard.Listener(on_press=al_apretar, on_release=al_soltar)
        oyente.daemon = True
        oyente.start()
        self._oyentes.append(oyente)

    # ------------------------------------------------------------------ flujo de un pedido
    def _activado(self) -> None:
        self.bandeja.estado("escuchando")
        audio.sonar(audio.SONIDO_ESCUCHO)

    def _pedido(self, datos) -> None:
        self.escucha.ocupado.set()
        self.trabajo.put(("voz", datos))

    def _trabajar(self) -> None:
        while True:
            tipo, dato = self.trabajo.get()
            preguntar = False
            try:
                if tipo == "voz":
                    preguntar = self._atender(dato)
                elif tipo == "aviso":
                    self._avisar(dato)
            except Exception:  # noqa: BLE001
                log.exception("Error atendiendo %s", tipo)
            finally:
                if self.escucha:
                    self.escucha.mic.vaciar()
                    if preguntar:
                        self.escucha.escuchar_respuesta()
                    self.escucha.ocupado.clear()
                self.bandeja.estado("escuchando" if preguntar else "esperando")

    def _atender(self, datos) -> bool:
        """Atiende un pedido. Devuelve True si Jarvis hizo una pregunta y espera respuesta."""
        self.bandeja.estado("pensando")
        texto = self.oido.transcribir(datos)
        log.info("Transcripción: %r", texto)
        resp: Respuesta = self.nucleo.procesar(texto)
        if resp.sonido_error:
            audio.sonar(audio.SONIDO_ERROR)
        self.bandeja.notificar(f"Vos: {texto or '(no se entendió)'}\nJarvis: {resp.decir}")
        self.boca.decir(resp.decir)
        return resp.preguntar

    def _sonar_aviso(self, aviso: Aviso) -> None:
        self.trabajo.put(("aviso", aviso))

    def _avisar(self, aviso: Aviso) -> None:
        if self.escucha:
            self.escucha.ocupado.set()
        frase = frase_aviso(aviso, datetime.now())
        self.bandeja.notificar(frase)
        repeticiones = 3 if aviso.tipo == "alarma" else 1
        for _ in range(repeticiones):
            audio.sonar(audio.SONIDO_ALARMA)
        self.boca.decir(frase)

    # ------------------------------------------------------------------ menú
    def _silenciar(self, valor: bool) -> None:
        if self.escucha:
            (self.escucha.silenciado.set if valor else self.escucha.silenciado.clear)()

    def modo_juego(self, activar: bool) -> None:
        if self.escucha:
            self.escucha.hey_jarvis_activo = (not activar) and self.escucha.detector is not None
        config.guardar_valor("modo_juego", bool(activar))
        self.cfg["modo_juego"] = bool(activar)
        self.bandeja.set_juego(bool(activar))

    def _probar_voz(self) -> None:
        if self.boca:
            threading.Thread(target=self.boca.decir,
                             args=("Hola, soy Jarvis. Si me escuchás bien, está todo funcionando.",), daemon=True).start()

    def salir(self) -> None:
        log.info("Saliendo")
        if self.escucha:
            self.escucha.detener()
        self.nucleo.agenda.detener()
        for o in self._oyentes:
            o.stop()


def main() -> None:
    _configurar_log()
    if not _una_sola_instancia():
        log.info("Jarvis ya estaba abierto.")
        return
    App().iniciar()


if __name__ == "__main__":
    main()

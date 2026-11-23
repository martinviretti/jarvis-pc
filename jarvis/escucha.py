"""Cuándo escuchar: 'Hey Jarvis' o tecla apretada. Corta la grabación cuando la persona deja de hablar."""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable

import numpy as np

from . import audio

log = logging.getLogger("jarvis")

SEG_POR_BLOQUE = audio.BLOQUE / audio.FS  # 0,08 s


def _rms(bloque: np.ndarray) -> float:
    x = bloque.astype(np.float32) / 32768.0
    return float(np.sqrt(np.mean(x * x)) + 1e-9)


class Escucha:
    """Hilo que lee el micrófono y entrega audio de cada pedido a `al_terminar(audio_int16)`.

    - Modo voz: después de "Hey Jarvis" graba hasta que hay ~0,8 s de silencio.
    - Modo tecla: graba mientras la tecla esté apretada.
    """

    def __init__(self, microfono: audio.Microfono, detector, al_activarse: Callable[[], None],
                 al_terminar: Callable[[np.ndarray], None]):
        self.mic = microfono
        self.detector = detector
        self.al_activarse = al_activarse
        self.al_terminar = al_terminar
        self.hey_jarvis_activo = detector is not None
        self.ocupado = threading.Event()     # mientras procesa o habla: no escucha
        self.silenciado = threading.Event()  # el usuario lo silenció desde la bandeja
        self._tecla = threading.Event()
        self._pedido_manual = threading.Event()  # para "¿sí o no?" sin repetir "Hey Jarvis"
        self._parar = threading.Event()
        self._piso_ruido = 0.003
        self._hilo = threading.Thread(target=self._bucle, name="escucha", daemon=True)

    # --- control desde afuera
    def iniciar(self) -> None:
        self.mic.abrir()
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        self.mic.cerrar()

    def tecla_apretada(self) -> None:
        if not self.silenciado.is_set() and not self.ocupado.is_set():
            self._tecla.set()

    def tecla_soltada(self) -> None:
        self._tecla.clear()

    def escuchar_respuesta(self) -> None:
        """Abre el micrófono para una respuesta corta (sí/no) sin necesitar 'Hey Jarvis'."""
        self._pedido_manual.set()

    # --- bucle
    def _bucle(self) -> None:
        previo: deque[np.ndarray] = deque(maxlen=4)  # 0,3 s antes de activarse
        while not self._parar.is_set():
            bloque = self.mic.leer(timeout=0.5)
            if bloque is None:
                continue
            if self.ocupado.is_set() or self.silenciado.is_set():
                previo.clear()
                if self.detector is not None:
                    self.detector.reiniciar()
                continue

            if self._tecla.is_set():
                self._grabar_con_tecla(list(previo) + [bloque])
                previo.clear()
                continue

            if self._pedido_manual.is_set():
                self._pedido_manual.clear()
                self._grabar_hasta_silencio([bloque], espera_max=5.0)
                previo.clear()
                continue

            nivel = _rms(bloque)
            self._piso_ruido = 0.98 * self._piso_ruido + 0.02 * min(nivel, 0.05)
            previo.append(bloque)

            if self.hey_jarvis_activo and self.detector is not None and self.detector.escuchar(bloque):
                self.detector.reiniciar()
                self.mic.vaciar()
                previo.clear()
                self.al_activarse()
                self.mic.vaciar()  # descarta el sonido del "tic"
                self._grabar_hasta_silencio([], espera_max=6.0)

    def _grabar_con_tecla(self, inicio: list[np.ndarray]) -> None:
        self.al_activarse()
        bloques = list(inicio)
        t0 = time.monotonic()
        while self._tecla.is_set() and time.monotonic() - t0 < 20:
            b = self.mic.leer(timeout=0.5)
            if b is not None:
                bloques.append(b)
        for _ in range(3):  # un pedacito después de soltar
            b = self.mic.leer(timeout=0.2)
            if b is not None:
                bloques.append(b)
        self._entregar(bloques)

    def _grabar_hasta_silencio(self, inicio: list[np.ndarray], espera_max: float) -> None:
        bloques = list(inicio)
        umbral = max(self._piso_ruido * 3.0, 0.006)
        hablo = False
        silencio = 0.0
        t0 = time.monotonic()
        while not self._parar.is_set():
            b = self.mic.leer(timeout=0.5)
            if b is None:
                continue
            bloques.append(b)
            dur = time.monotonic() - t0
            if _rms(b) > umbral:
                hablo = True
                silencio = 0.0
            else:
                silencio += SEG_POR_BLOQUE
            if hablo and silencio >= 0.8:
                break
            if not hablo and dur >= espera_max:
                log.info("Se activó pero nadie habló.")
                audio.sonar(audio.SONIDO_LISTO)
                return
            if dur >= 12:
                break
        self._entregar(bloques)

    def _entregar(self, bloques: list[np.ndarray]) -> None:
        if not bloques:
            return
        datos = np.concatenate(bloques)
        if datos.size < audio.FS * 0.4:
            return
        self.al_terminar(datos)

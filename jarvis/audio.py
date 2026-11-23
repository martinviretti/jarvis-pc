"""Micrófono (HyperX) y reproducción por la salida de audio activa de Windows."""

from __future__ import annotations

import logging
import queue
import threading

import numpy as np
import sounddevice as sd

log = logging.getLogger("jarvis")

FS = 16000          # frecuencia del micrófono (lo que esperan los modelos)
BLOQUE = 1280       # 80 ms por bloque, el tamaño que usa openWakeWord


def listar_microfonos() -> list[tuple[int, str]]:
    """Micrófonos de la API de audio por defecto (MME), sin duplicados."""
    salida = []
    try:
        hostapi = sd.default.hostapi
    except Exception:  # noqa: BLE001
        hostapi = 0
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and d["hostapi"] == hostapi:
            salida.append((i, d["name"]))
    return salida


def buscar_microfono(parte_nombre: str | None) -> int | None:
    """Índice del micrófono cuyo nombre contiene `parte_nombre` (por ejemplo 'HyperX')."""
    if not parte_nombre:
        return None
    buscado = parte_nombre.lower()
    for i, nombre in listar_microfonos():
        if buscado in nombre.lower():
            return i
    # probar en todas las APIs de audio
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0 and buscado in d["name"].lower():
            return i
    return None


class Microfono:
    """Lee el micrófono en bloques de 80 ms y los deja en una cola."""

    def __init__(self, parte_nombre: str | None):
        self.indice = buscar_microfono(parte_nombre)
        if parte_nombre and self.indice is None:
            log.warning("No encontré un micrófono con '%s'; uso el predeterminado de Windows.", parte_nombre)
        self.nombre = sd.query_devices(self.indice if self.indice is not None else sd.default.device[0])["name"]
        self.cola: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)
        self._stream: sd.InputStream | None = None

    def _callback(self, indata, frames, tiempo, status):  # noqa: ARG002
        if status:
            log.debug("mic: %s", status)
        try:
            self.cola.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass

    def abrir(self) -> None:
        self._stream = sd.InputStream(
            samplerate=FS, channels=1, dtype="int16", blocksize=BLOQUE,
            device=self.indice, callback=self._callback,
        )
        self._stream.start()
        log.info("Micrófono: %s", self.nombre)

    def cerrar(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def vaciar(self) -> None:
        while not self.cola.empty():
            try:
                self.cola.get_nowait()
            except queue.Empty:
                break

    def leer(self, timeout: float = 1.0) -> np.ndarray | None:
        try:
            return self.cola.get(timeout=timeout)
        except queue.Empty:
            return None


# ---------------------------------------------------------------- sonidos

_lock_salida = threading.Lock()
volumen = 0.9  # se ajusta desde la config


def reproducir(audio: np.ndarray, fs: int) -> None:
    """Reproduce int16 o float por la salida de audio activa de Windows (casco o monitor)."""
    if audio.dtype == np.int16:
        datos = audio.astype(np.float32) / 32768.0
    else:
        datos = audio.astype(np.float32)
    datos = np.clip(datos * volumen, -1.0, 1.0)
    with _lock_salida:
        try:
            sd.play(datos, fs, blocking=True)
        except Exception as e:  # noqa: BLE001
            log.error("No pude reproducir audio: %s", e)


def _tono(frecuencias: list[tuple[float, float]], fs: int = 22050, amp: float = 0.35) -> np.ndarray:
    partes = []
    for f, dur in frecuencias:
        n = int(fs * dur)
        t = np.arange(n) / fs
        if f <= 0:
            partes.append(np.zeros(n, dtype=np.float32))
            continue
        env = np.minimum(1.0, np.minimum(t / 0.008, (dur - t) / 0.03))
        onda = np.sin(2 * np.pi * f * t) * 0.8 + np.sin(4 * np.pi * f * t) * 0.15
        partes.append((onda * env * amp).astype(np.float32))
    return np.concatenate(partes)


SONIDO_ESCUCHO = _tono([(880, 0.07), (1320, 0.09)])
SONIDO_LISTO = _tono([(1100, 0.06), (740, 0.08)], amp=0.25)
SONIDO_ERROR = _tono([(330, 0.15), (247, 0.2)], amp=0.3)
SONIDO_ALARMA = _tono([(988, 0.18), (0, 0.06), (988, 0.18), (0, 0.06), (1319, 0.35), (0, 0.4)] * 2)


def sonar(sonido: np.ndarray) -> None:
    reproducir(sonido, 22050)

"""Oído (Parakeet v3, voz a texto) y boca (Piper, texto a voz). Todo en el procesador: cero VRAM."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

import numpy as np

from . import audio
from .config import MODELOS

log = logging.getLogger("jarvis")

MODELO_STT = "nemo-parakeet-tdt-0.6b-v3"
CARPETA_STT = MODELOS / "parakeet"
CARPETA_VOCES = MODELOS / "voces"
CARPETA_WAKE = MODELOS / "hey_jarvis"


def _limitar_hilos(opciones) -> None:
    # Dos hilos alcanzan y no le quitan procesador a un juego.
    opciones.intra_op_num_threads = 2
    opciones.inter_op_num_threads = 1


class Oido:
    def __init__(self) -> None:
        import onnx_asr
        import onnxruntime as ort

        opciones = ort.SessionOptions()
        _limitar_hilos(opciones)
        self._modelo = onnx_asr.load_model(
            MODELO_STT, str(CARPETA_STT), quantization="int8",
            providers=["CPUExecutionProvider"], sess_options=opciones,
        )
        self._lock = threading.Lock()

    def transcribir(self, audio_int16: np.ndarray) -> str:
        if audio_int16.size < audio.FS * 0.3:
            return ""
        x = audio_int16.astype(np.float32) / 32768.0
        with self._lock:
            texto = self._modelo.recognize(x, sample_rate=audio.FS)
        return (texto or "").strip()


class Boca:
    def __init__(self, voz: str, velocidad: float = 1.0) -> None:
        from piper import PiperVoice
        from piper.config import SynthesisConfig

        ruta = CARPETA_VOCES / f"{voz}.onnx"
        if not ruta.exists():
            raise FileNotFoundError(f"No está la voz {ruta}. Corré el instalador de nuevo.")
        self._voz = PiperVoice.load(str(ruta))
        self._cfg = SynthesisConfig(length_scale=float(velocidad))
        self.fs = self._voz.config.sample_rate
        self._lock = threading.Lock()

    def sintetizar(self, texto: str) -> np.ndarray:
        with self._lock:
            partes = [c.audio_int16_array for c in self._voz.synthesize(texto, syn_config=self._cfg)]
        if not partes:
            return np.zeros(0, dtype=np.int16)
        silencio = np.zeros(int(self.fs * 0.12), dtype=np.int16)
        return np.concatenate([silencio] + partes)

    def decir(self, texto: str) -> None:
        if not texto:
            return
        audio.reproducir(self.sintetizar(texto), self.fs)


class DetectorHeyJarvis:
    def __init__(self, sensibilidad: float = 0.5) -> None:
        from openwakeword.model import Model

        self.umbral = float(sensibilidad)
        self._modelo = Model(
            wakeword_models=[str(CARPETA_WAKE / "hey_jarvis_v0.1.onnx")],
            inference_framework="onnx",
            melspec_model_path=str(CARPETA_WAKE / "melspectrogram.onnx"),
            embedding_model_path=str(CARPETA_WAKE / "embedding_model.onnx"),
        )

    def escuchar(self, bloque: np.ndarray) -> bool:
        puntajes = self._modelo.predict(bloque)
        return max(puntajes.values(), default=0.0) >= self.umbral

    def reiniciar(self) -> None:
        self._modelo.reset()


def modelos_presentes(voz: str) -> list[str]:
    """Qué modelos faltan, para avisar en vez de fallar."""
    faltan = []
    if not (CARPETA_VOCES / f"{voz}.onnx").exists():
        faltan.append(f"voz {voz}")
    if not (CARPETA_WAKE / "hey_jarvis_v0.1.onnx").exists():
        faltan.append("Hey Jarvis")
    if not any(Path(CARPETA_STT).glob("encoder-model*.onnx")):
        faltan.append("Parakeet")
    return faltan

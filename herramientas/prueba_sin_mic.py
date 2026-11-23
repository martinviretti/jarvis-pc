"""Prueba de punta a punta sin micrófono: la voz de Piper dice 'Hey Jarvis' + una orden,
y se la pasamos a Jarvis como si viniera del casco. Sirve para chequear que todo esté bien instalado.

    python herramientas/prueba_sin_mic.py "poné un timer de diez minutos"
"""

from __future__ import annotations

import queue
import sys
import threading
import time

import numpy as np
from scipy.signal import resample_poly

from jarvis import audio, config
from jarvis.escucha import Escucha
from jarvis.nucleo import Nucleo
from jarvis.voz import Boca, DetectorHeyJarvis, Oido


class MicFalso:
    def __init__(self, datos: np.ndarray):
        self.cola: queue.Queue = queue.Queue()
        self.nombre = "micrófono falso"
        for i in range(0, len(datos) - audio.BLOQUE, audio.BLOQUE):
            self.cola.put(datos[i:i + audio.BLOQUE])

    def abrir(self): ...
    def cerrar(self): ...
    def vaciar(self): ...

    def leer(self, timeout=1.0):
        try:
            return self.cola.get(timeout=timeout)
        except queue.Empty:
            return None


def a_16k(boca: Boca, texto: str) -> np.ndarray:
    a = boca.sintetizar(texto).astype(np.float32)
    return resample_poly(a, 160, boca.fs // 100).astype(np.int16)


def main() -> int:
    orden = sys.argv[1] if len(sys.argv) > 1 else "poné un timer de diez minutos"
    cfg = config.cargar()
    print("Cargando modelos...")
    boca = Boca(cfg["voz"])
    oido = Oido()
    detector = DetectorHeyJarvis(float(cfg.get("sensibilidad_hey_jarvis", 0.5)))
    silencio = np.zeros(int(audio.FS * 1.2), dtype=np.int16)
    ruido = (np.random.default_rng(0).normal(0, 30, audio.FS * 2)).astype(np.int16)
    # "Hey Jarvis" funciona mejor pronunciado como en inglés: si está la voz inglesa, la usamos para eso.
    from jarvis.voz import CARPETA_VOCES

    voz_hey = Boca("en_US-lessac-medium") if (CARPETA_VOCES / "en_US-lessac-medium.onnx").exists() else boca
    senal = np.concatenate([ruido, a_16k(voz_hey, "Hey Jarvis."), silencio[:4000], a_16k(boca, orden), silencio, silencio])

    resultado: dict = {}
    listo = threading.Event()

    def al_terminar(datos):
        t = time.time()
        resultado["texto"] = oido.transcribir(datos)
        resultado["seg_stt"] = time.time() - t
        listo.set()

    esc = Escucha(MicFalso(senal), detector, lambda: print("  [Hey Jarvis detectado]"), al_terminar)
    audio.sonar = lambda _s: None  # sin sonidos en la prueba
    esc.iniciar()
    if not listo.wait(30):
        print("No se detectó 'Hey Jarvis' con la voz sintética (con voz real suele andar mejor).")
        print("Probando la orden directo, sin palabra de activación...")
        resultado["texto"] = oido.transcribir(a_16k(boca, orden))
        resultado["seg_stt"] = 0
    esc.detener()
    texto = resultado["texto"]
    nucleo = Nucleo(cfg, lambda _a: None)
    resp = nucleo.procesar(texto)
    print(f"  Dijo:      {orden!r}")
    print(f"  Entendió:  {texto!r}  ({resultado['seg_stt']:.2f} s)")
    print(f"  Jarvis:    {resp.decir!r}")
    nucleo.agenda.cancelar(todos=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

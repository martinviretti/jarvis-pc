"""Descarga los modelos (una sola vez): voz Piper, Hey Jarvis y Parakeet. Unos 800 MB en total."""

from __future__ import annotations

import sys

from . import config
from .voz import CARPETA_STT, CARPETA_VOCES, CARPETA_WAKE, MODELO_STT


def main() -> int:
    config.asegurar_carpetas()
    cfg = config.cargar()
    voz = cfg.get("voz", "es_AR-daniela-high")

    print(f"[1/3] Voz {voz} (~110 MB)...", flush=True)
    CARPETA_VOCES.mkdir(parents=True, exist_ok=True)
    if not (CARPETA_VOCES / f"{voz}.onnx").exists():
        from piper.download_voices import download_voice

        download_voice(voz, CARPETA_VOCES)
    print("      lista.", flush=True)

    print("[2/3] Detector de 'Hey Jarvis' (~5 MB)...", flush=True)
    CARPETA_WAKE.mkdir(parents=True, exist_ok=True)
    if not (CARPETA_WAKE / "hey_jarvis_v0.1.onnx").exists():
        import openwakeword.utils as owu

        owu.download_models(["hey_jarvis"], target_directory=str(CARPETA_WAKE))
    print("      listo.", flush=True)

    print("[3/3] Parakeet, para entender español (~650 MB, puede tardar unos minutos)...", flush=True)
    import onnx_asr

    onnx_asr.load_model(MODELO_STT, str(CARPETA_STT), quantization="int8")
    print("      listo.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

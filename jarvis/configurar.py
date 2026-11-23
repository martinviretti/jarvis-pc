"""Asistente de configuración por consola: micrófono, tecla, Hey Jarvis, luz y Google.

Uso:
    python -m jarvis.configurar            configuración completa
    python -m jarvis.configurar --google   solo conectar Google
    python -m jarvis.configurar --calibrar calibrar 'Hey Jarvis' con la voz de quien lo usa
"""

from __future__ import annotations

import sys
import time

from . import config


def _preguntar(texto: str, defecto: str = "") -> str:
    extra = f" [{defecto}]" if defecto else ""
    r = input(f"{texto}{extra}: ").strip()
    return r or defecto


def _si_no(texto: str, defecto: bool = True) -> bool:
    d = "S/n" if defecto else "s/N"
    r = input(f"{texto} ({d}): ").strip().lower()
    if not r:
        return defecto
    return r.startswith(("s", "y"))


def elegir_microfono(cfg: dict) -> None:
    from . import audio

    print("\n=== 1. Micrófono ===")
    mics = audio.listar_microfonos()
    if not mics:
        print("No encontré micrófonos. Conectá el casco y volvé a correr la configuración.")
        return
    sugerido = audio.buscar_microfono(cfg.get("microfono") or "HyperX")
    for n, (i, nombre) in enumerate(mics, 1):
        marca = "  <- sugerido" if i == sugerido else ""
        print(f"  {n}. {nombre}{marca}")
    defecto = next((str(n) for n, (i, _) in enumerate(mics, 1) if i == sugerido), "1")
    elegido = _preguntar("Número del micrófono del casco", defecto)
    try:
        nombre = mics[int(elegido) - 1][1]
    except (ValueError, IndexError):
        nombre = mics[0][1]
    # guardamos una parte del nombre, así sigue andando si cambia el número del dispositivo
    parte = nombre.split("(")[-1].rstrip(")").strip() if "(" in nombre else nombre
    config.guardar_valor("microfono", parte or nombre)
    cfg["microfono"] = parte or nombre
    print(f"Listo: {nombre}")

    if _si_no("¿Probamos el micrófono? Vas a hablar 4 segundos", True):
        probar_microfono(cfg)


def probar_microfono(cfg: dict) -> None:
    import numpy as np
    import sounddevice as sd

    from . import audio

    idx = audio.buscar_microfono(cfg.get("microfono"))
    print("Hablá ahora, por ejemplo: 'poné un timer de diez minutos'...")
    grab = sd.rec(int(4 * audio.FS), samplerate=audio.FS, channels=1, dtype="int16", device=idx)
    sd.wait()
    datos = grab[:, 0]
    nivel = float(np.sqrt(np.mean((datos.astype(np.float32) / 32768) ** 2)))
    print(f"Nivel: {nivel:.3f}", "(bien)" if nivel > 0.01 else "(muy bajo: revisá que el micrófono del casco no esté silenciado)")
    print("Transcribiendo (la primera vez tarda unos segundos)...")
    from .voz import Oido

    texto = Oido().transcribir(datos)
    print(f"Entendí: {texto!r}")


def elegir_tecla(cfg: dict) -> None:
    from pynput import keyboard, mouse

    print("\n=== 2. Tecla para hablar ===")
    print("Apretá la tecla o el botón lateral del mouse que quieras usar (tenés 10 segundos).")
    print("Recomendado: F9, F10 o un botón lateral del mouse. Si no apretás nada, queda F9.")
    elegido: list[str] = []

    def tecla(k):
        if isinstance(k, keyboard.Key):
            elegido.append(k.name)
        elif getattr(k, "char", None):
            elegido.append(k.char.lower())
        return False

    def click(_x, _y, boton, apretado):
        if apretado and boton.name in ("x1", "x2", "middle"):
            elegido.append(f"mouse_{boton.name}")
            return False
        return None

    with keyboard.Listener(on_press=tecla) as kl, mouse.Listener(on_click=click) as ml:
        t0 = time.time()
        while not elegido and time.time() - t0 < 10:
            time.sleep(0.05)
        kl.stop()
        ml.stop()
    valor = elegido[0] if elegido else "f9"
    if valor in ("enter", "space", "esc", "shift", "ctrl", "alt", "tab"):
        print(f"'{valor}' no conviene (la usás para otras cosas). Queda F9.")
        valor = "f9"
    config.guardar_valor("tecla_hablar", valor)
    print(f"Tecla para hablar: {valor}")


def elegir_hey_jarvis(cfg: dict) -> None:
    print("\n=== 3. 'Hey Jarvis' ===")
    activo = _si_no("¿Querés activarlo diciendo 'Hey Jarvis' además de la tecla?", True)
    config.guardar_valor("hey_jarvis", activo)
    if activo and _si_no("¿Lo calibramos con tu voz? (recomendado, tarda 30 segundos)", True):
        calibrar_hey_jarvis(cfg)


def _puntaje_max(detector, datos) -> float:
    from . import audio

    detector.reiniciar()
    mx = 0.0
    for i in range(0, len(datos) - audio.BLOQUE, audio.BLOQUE):
        mx = max(mx, max(detector._modelo.predict(datos[i:i + audio.BLOQUE]).values()))  # noqa: SLF001
    return mx


def calibrar_hey_jarvis(cfg: dict) -> None:
    """Graba 3 'Hey Jarvis' y un rato de charla normal, y ajusta la sensibilidad a esa voz."""
    import sounddevice as sd

    from . import audio
    from .voz import DetectorHeyJarvis

    idx = audio.buscar_microfono(cfg.get("microfono"))
    detector = DetectorHeyJarvis(0.5)
    print("Tip: decilo como en inglés, 'jei YAR-vis', con ganas y sin apurarte.")
    puntajes = []
    for n in range(1, 4):
        input(f"  [{n}/3] Apretá Enter y decí 'Hey Jarvis'...")
        grab = sd.rec(int(2.5 * audio.FS), samplerate=audio.FS, channels=1, dtype="int16", device=idx)
        sd.wait()
        p = _puntaje_max(detector, grab[:, 0])
        puntajes.append(p)
        print(f"        puntaje: {p:.2f}")
    input("  Ahora apretá Enter y hablá normal 5 segundos SIN decir 'Hey Jarvis' (contá algo del día)...")
    grab = sd.rec(int(5 * audio.FS), samplerate=audio.FS, channels=1, dtype="int16", device=idx)
    sd.wait()
    ruido = _puntaje_max(detector, grab[:, 0])
    print(f"        puntaje hablando normal: {ruido:.2f}")
    minimo = min(puntajes)
    umbral = max(0.15, min(0.6, minimo * 0.6))
    if umbral <= ruido * 1.3:
        umbral = min(0.8, max(umbral, ruido * 1.5))
    if minimo < 0.2:
        print("Jarvis te reconoce poco. Probá decirlo más claro, más cerca del micrófono, o usá la tecla.")
    config.guardar_valor("sensibilidad_hey_jarvis", round(float(umbral), 2))
    print(f"Sensibilidad ajustada a {umbral:.2f}.")


def elegir_luz(cfg: dict) -> None:
    print("\n=== 4. Luz de la pieza ===")
    if not _si_no("¿Ya tienen una lámpara WiZ o un enchufe Shelly instalado?", False):
        print("Ok, se configura después (corré esta configuración de nuevo).")
        return
    tipo = _preguntar("Tipo (wiz o shelly)", "wiz").lower()
    ip = _preguntar("IP de la lámpara o enchufe (la muestra la app del fabricante o el router)")
    config.guardar_seccion("luz", {"tipo": tipo, "ip": ip})
    from .acciones import luz

    try:
        luz.cambiar({"tipo": tipo, "ip": ip}, True)
        time.sleep(1)
        luz.cambiar({"tipo": tipo, "ip": ip}, False)
        print("La luz respondió (se prendió y se apagó).")
    except Exception as e:  # noqa: BLE001
        print(f"No respondió ({e}). Revisá la IP y que esté en la misma red.")


def conectar_google(cfg: dict) -> None:
    from .acciones import google_svc as gg

    print("\n=== Conectar Google (calendario y tareas) ===")
    if not config.GOOGLE_CRED_PATH.exists():
        print("Primero hay que descargar el archivo de credenciales de Google (se hace una vez).")
        print("Seguí la sección 'Conectar Google' del README y guardá el archivo como:")
        print(f"   {config.GOOGLE_CRED_PATH}")
        input("Cuando lo tengas ahí, apretá Enter (o cerrá esta ventana para hacerlo después)...")
        if not config.GOOGLE_CRED_PATH.exists():
            print("Todavía no está el archivo. Volvé a intentarlo desde el menú de Jarvis: Conectar Google.")
            return
    print("Se va a abrir el navegador: iniciá sesión con la cuenta de Google de tu hijo y aceptá los permisos.")
    print("Si aparece 'Google no verificó esta app', tocá Configuración avanzada > Ir a Jarvis (es tu propia app).")
    gg.iniciar_sesion()
    g = dict(cfg.get("google", {}))
    g["activado"] = True
    config.guardar_seccion("google", g)
    try:
        gg.listar_tareas(1)
        print("Conectado. Jarvis ya puede usar el calendario y las tareas. Reiniciá Jarvis para que lo tome.")
    except Exception as e:  # noqa: BLE001
        print(f"Se conectó pero falló una prueba: {e}")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cfg = config.cargar()
    try:
        if "--google" in argv:
            conectar_google(cfg)
        elif "--mic" in argv:
            probar_microfono(cfg)
        elif "--calibrar" in argv:
            calibrar_hey_jarvis(cfg)
        else:
            print("Configuración de Jarvis. Podés repetirla cuando quieras.")
            elegir_microfono(cfg)
            elegir_tecla(cfg)
            elegir_hey_jarvis(cfg)
            elegir_luz(cfg)
            if _si_no("\n¿Conectamos Google ahora (calendario y tareas)?", False):
                conectar_google(cfg)
            print(f"\nListo. La configuración quedó en {config.CONFIG_PATH}")
            print("Ahí también podés agregar apps para abrir por voz.")
    except KeyboardInterrupt:
        print("\nCancelado.")
    input("\nApretá Enter para cerrar...")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Rutas y configuración de Jarvis."""

from __future__ import annotations

import logging
import os
import shutil
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

log = logging.getLogger("jarvis")


def carpeta_base() -> Path:
    """Carpeta de instalación: %LOCALAPPDATA%\\JarvisPC (o JARVIS_HOME si está definida)."""
    env = os.environ.get("JARVIS_HOME")
    if env:
        return Path(env)
    return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "JarvisPC"


BASE = carpeta_base()
DATOS = BASE / "datos"
MODELOS = BASE / "modelos"
CONFIG_PATH = DATOS / "config.yaml"
LOG_PATH = DATOS / "jarvis.log"
HISTORIAL_PATH = DATOS / "historial.jsonl"
ALARMAS_PATH = DATOS / "alarmas.json"
GOOGLE_CRED_PATH = DATOS / "google_credenciales.json"
GOOGLE_TOKEN_PATH = DATOS / "google_token.json"


def _default_text() -> str:
    return resources.files("jarvis").joinpath("config_default.yaml").read_text(encoding="utf-8")


def _defaults() -> dict[str, Any]:
    return yaml.safe_load(_default_text())


def _merge(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def asegurar_carpetas() -> None:
    DATOS.mkdir(parents=True, exist_ok=True)
    MODELOS.mkdir(parents=True, exist_ok=True)


def cargar() -> dict[str, Any]:
    """Lee config.yaml; si no existe, lo crea con los valores por defecto."""
    asegurar_carpetas()
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(_default_text(), encoding="utf-8")
    try:
        usuario = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as e:
        log.error("config.yaml tiene un error, uso los valores por defecto: %s", e)
        respaldo = CONFIG_PATH.with_suffix(".yaml.roto")
        shutil.copy(CONFIG_PATH, respaldo)
        usuario = {}
    return _merge(_defaults(), usuario)


def guardar_valor(clave: str, valor: Any) -> None:
    """Cambia una clave de primer nivel conservando los comentarios del archivo."""
    asegurar_carpetas()
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(_default_text(), encoding="utf-8")
    lineas = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    nuevo = f"{clave}: {yaml.safe_dump(valor, allow_unicode=True, default_flow_style=True).strip().removesuffix('...').strip()}"
    for i, linea in enumerate(lineas):
        if linea.startswith(f"{clave}:"):
            lineas[i] = nuevo
            break
    else:
        lineas.append(nuevo)
    CONFIG_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")


def guardar_seccion(clave: str, valor: dict) -> None:
    """Reemplaza una sección (por ejemplo 'luz' o 'google') manteniendo el resto del archivo."""
    asegurar_carpetas()
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(_default_text(), encoding="utf-8")
    lineas = CONFIG_PATH.read_text(encoding="utf-8").splitlines()
    bloque = yaml.safe_dump({clave: valor}, allow_unicode=True, sort_keys=False).rstrip().splitlines()
    inicio = next((i for i, l in enumerate(lineas) if l.startswith(f"{clave}:")), None)
    if inicio is None:
        lineas += [""] + bloque
    else:
        fin = inicio + 1
        while fin < len(lineas) and (lineas[fin].startswith((" ", "\t")) or not lineas[fin].strip()):
            if not lineas[fin].strip() and fin + 1 < len(lineas) and not lineas[fin + 1].startswith((" ", "\t")):
                break
            fin += 1
        lineas[inicio:fin] = bloque
    CONFIG_PATH.write_text("\n".join(lineas) + "\n", encoding="utf-8")

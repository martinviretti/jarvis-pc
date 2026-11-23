"""Luz de la pieza con control dentro de la casa (sin la nube del fabricante): WiZ o Shelly."""

from __future__ import annotations

import json
import socket

import requests


class LuzNoConfigurada(Exception):
    pass


def _wiz(ip: str, params: dict) -> None:
    msg = json.dumps({"id": 1, "method": "setPilot", "params": params}).encode()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(2)
        s.sendto(msg, (ip, 38899))
        s.recvfrom(1024)  # la lámpara confirma; si no contesta, salta timeout


def _shelly(ip: str, encender: bool) -> None:
    # Shelly Gen2/Gen3 (Plus, Pro, Mini) usan RPC; los Gen1, /relay/0.
    try:
        r = requests.get(f"http://{ip}/rpc/Switch.Set", params={"id": 0, "on": str(encender).lower()}, timeout=3)
        if r.ok:
            return
    except requests.RequestException:
        pass
    r = requests.get(f"http://{ip}/relay/0", params={"turn": "on" if encender else "off"}, timeout=3)
    r.raise_for_status()


def cambiar(cfg_luz: dict, encender: bool, brillo: int | None = None) -> None:
    tipo = (cfg_luz or {}).get("tipo", "ninguna")
    ip = (cfg_luz or {}).get("ip", "")
    if tipo not in ("wiz", "shelly") or not ip:
        raise LuzNoConfigurada
    if tipo == "wiz":
        params: dict = {"state": encender}
        if encender and brillo is not None:
            params["dimming"] = max(10, min(100, brillo))
        _wiz(ip, params)
    else:
        _shelly(ip, encender)

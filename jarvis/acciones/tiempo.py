"""Timers, alarmas y recordatorios locales. Se guardan en disco para sobrevivir a un reinicio."""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

log = logging.getLogger("jarvis")


@dataclass
class Aviso:
    id: str
    tipo: str          # "timer" | "alarma" | "recordatorio"
    cuando: str        # ISO local
    texto: str = ""
    duracion: int = 0  # segundos, solo timers

    @property
    def dt(self) -> datetime:
        return datetime.fromisoformat(self.cuando)


class Agenda:
    def __init__(self, ruta: Path, al_sonar: Callable[[Aviso], None]):
        self.ruta = ruta
        self.al_sonar = al_sonar
        self._avisos: list[Aviso] = []
        self._lock = threading.Lock()
        self._parar = threading.Event()
        self._cargar()
        self._hilo = threading.Thread(target=self._bucle, name="agenda", daemon=True)

    def iniciar(self) -> None:
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()

    # --- persistencia
    def _cargar(self) -> None:
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            self._avisos = [Aviso(**d) for d in datos]
        except FileNotFoundError:
            self._avisos = []
        except Exception as e:  # noqa: BLE001
            log.error("No pude leer las alarmas guardadas: %s", e)
            self._avisos = []
        ahora = datetime.now()
        # Los timers vencidos con la PC apagada ya no tienen sentido; las alarmas y recordatorios
        # vencidos hace menos de 10 minutos se avisan igual.
        self._avisos = [
            a for a in self._avisos
            if a.dt > ahora or (a.tipo != "timer" and (ahora - a.dt).total_seconds() < 600)
        ]

    def _guardar(self) -> None:
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.ruta.with_suffix(".tmp")
        tmp.write_text(json.dumps([asdict(a) for a in self._avisos], ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.ruta)

    # --- operaciones
    def agregar(self, tipo: str, cuando: datetime, texto: str = "", duracion: int = 0) -> Aviso:
        aviso = Aviso(id=uuid.uuid4().hex[:8], tipo=tipo, cuando=cuando.isoformat(timespec="seconds"),
                      texto=texto, duracion=duracion)
        with self._lock:
            self._avisos.append(aviso)
            self._guardar()
        return aviso

    def listar(self, tipo: str | None = None) -> list[Aviso]:
        with self._lock:
            lista = [a for a in self._avisos if tipo is None or a.tipo == tipo]
        return sorted(lista, key=lambda a: a.dt)

    def cancelar(self, tipo: str | None = None, todos: bool = False) -> list[Aviso]:
        """Cancela el próximo aviso del tipo (o todos). Devuelve los cancelados."""
        with self._lock:
            candidatos = sorted((a for a in self._avisos if tipo is None or a.tipo == tipo), key=lambda a: a.dt)
            if not candidatos:
                return []
            quitar = candidatos if todos else candidatos[:1]
            ids = {a.id for a in quitar}
            self._avisos = [a for a in self._avisos if a.id not in ids]
            self._guardar()
        return quitar

    def _bucle(self) -> None:
        while not self._parar.wait(0.5):
            ahora = datetime.now()
            vencidos = []
            with self._lock:
                for a in list(self._avisos):
                    if a.dt <= ahora:
                        vencidos.append(a)
                        self._avisos.remove(a)
                if vencidos:
                    self._guardar()
            for a in vencidos:
                try:
                    self.al_sonar(a)
                except Exception:  # noqa: BLE001
                    log.exception("Error al hacer sonar un aviso")

"""Tests del núcleo con reloj fijo y sin Google, luz ni micrófono."""

from datetime import datetime

import pytest

AHORA = datetime(2026, 11, 23, 15, 0)


@pytest.fixture
def nucleo(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path))
    import importlib

    from jarvis import config

    importlib.reload(config)
    from jarvis import nucleo as mod

    importlib.reload(mod)
    cfg = config.cargar()
    avisos = []
    n = mod.Nucleo(cfg, avisos.append, ahora=lambda: AHORA)
    n._avisos_test = avisos
    return n


def test_timer_y_cuanto_falta(nucleo):
    r = nucleo.procesar("poné un timer de diez minutos")
    assert "10 minutos" in r.decir
    assert "Faltan 10 minutos" in nucleo.procesar("cuánto falta").decir
    assert nucleo.procesar("cancelá el timer").decir == "Timer cancelado."


def test_alarma(nucleo):
    r = nucleo.procesar("alarma a las siete")
    assert "mañana a las 7 en punto" in r.decir
    assert "7 en punto" in nucleo.procesar("qué alarmas tengo").decir


def test_recordatorio_local_sin_google(nucleo):
    r = nucleo.procesar("recordame mañana a las cinco llevar la carpeta")
    assert "17 en punto" in r.decir and "llevar la carpeta" in r.decir
    assert nucleo.agenda.listar("recordatorio")[0].dt == datetime(2026, 11, 24, 17, 0)


def test_suspender_pide_confirmacion(nucleo, monkeypatch):
    from jarvis.acciones import pc

    llamado = []
    monkeypatch.setattr(pc, "suspender", lambda: llamado.append(True))
    r = nucleo.procesar("suspendé la PC")
    assert r.preguntar
    r2 = nucleo.procesar("no")
    assert "no hago nada" in r2.decir
    assert not llamado


def test_tareas_sin_google_avisa(nucleo):
    r = nucleo.procesar("anotá estudiar matemática")
    assert "Google" in r.decir


def test_app_desconocida(nucleo):
    assert "lista de apps" in nucleo.procesar("abrí fortnite").decir


def test_hora(nucleo):
    assert nucleo.procesar("qué hora es").decir == "Son las 15 en punto."

"""El cerebro de Jarvis: recibe el texto, ejecuta la orden y devuelve qué decir."""

from __future__ import annotations

import json
import logging
import random
import re
import threading
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from . import config, texto as tx
from .acciones import clima, luz, pc
from .acciones import google_svc as gg
from .acciones.tiempo import Agenda, Aviso
from .intents import Intent, interpretar, preparar

log = logging.getLogger("jarvis")

AYUDA = (
    "Puedo poner timers y alarmas, anotar tareas, agregar cosas al calendario y decirte qué tenés hoy. "
    "También manejo la música, el volumen, busco en YouTube, abro tus apps, te digo el clima, "
    "prendo y apago la luz, y suspendo o apago la PC. Por ejemplo: poné un timer de diez minutos."
)


@dataclass
class Respuesta:
    decir: str
    preguntar: bool = False   # si True, Jarvis escucha la respuesta sin "Hey Jarvis"
    sonido_error: bool = False


class Nucleo:
    def __init__(self, cfg: dict, avisar: Callable[[Aviso], None],
                 notificar: Callable[[str], None] | None = None,
                 cambiar_modo_juego: Callable[[bool], None] | None = None,
                 ahora: Callable[[], datetime] = datetime.now):
        self.cfg = cfg
        self.ahora = ahora
        self.notificar = notificar or (lambda _t: None)
        self.cambiar_modo_juego = cambiar_modo_juego or (lambda _v: None)
        self.agenda = Agenda(config.ALARMAS_PATH, avisar)
        self._pendiente: tuple[str, Callable[[], str]] | None = None  # (pregunta, acción si dice sí)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ entrada principal
    def procesar(self, texto_oido: str) -> Respuesta:
        with self._lock:
            intent = interpretar(texto_oido)
            log.info("Oí: %r -> %s %s", texto_oido, intent.nombre, intent.datos)
            try:
                resp = self._despachar(intent)
            except gg.GoogleNoConfigurado:
                resp = Respuesta("Todavía no estoy conectado a Google. Hay que configurarlo una vez desde el menú de Jarvis.",
                                 sonido_error=True)
            except luz.LuzNoConfigurada:
                resp = Respuesta("Todavía no tengo una luz configurada.", sonido_error=True)
            except Exception:  # noqa: BLE001
                log.exception("Error ejecutando %s", intent.nombre)
                resp = Respuesta("Uy, algo falló al hacer eso. Probá de nuevo en un rato.", sonido_error=True)
            self._historial(texto_oido, intent, resp)
            return resp

    def _despachar(self, it: Intent) -> Respuesta:
        # Si estaba esperando un sí o un no
        if self._pendiente is not None:
            pregunta, accion = self._pendiente
            self._pendiente = None
            if it.nombre == "si":
                return Respuesta(accion())
            if it.nombre in ("no", "vacio", "no_entendi"):
                return Respuesta("Listo, no hago nada.")
            # dijo otra orden: se olvida la pregunta y sigue

        manejador = getattr(self, f"_i_{it.nombre}", None)
        if manejador is None:
            return Respuesta("No entendí. Decí: qué podés hacer, y te cuento.", sonido_error=True)
        resultado = manejador(it)
        return resultado if isinstance(resultado, Respuesta) else Respuesta(resultado)

    def _confirmar(self, pregunta: str, accion: Callable[[], str]) -> Respuesta:
        self._pendiente = (pregunta, accion)
        return Respuesta(pregunta, preguntar=True)

    def _historial(self, oido: str, it: Intent, resp: Respuesta) -> None:
        if not self.cfg.get("historial", True):
            return
        try:
            config.HISTORIAL_PATH.parent.mkdir(parents=True, exist_ok=True)
            with config.HISTORIAL_PATH.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"cuando": self.ahora().isoformat(timespec="seconds"), "oyo": oido,
                                    "orden": it.nombre, "respuesta": resp.decir}, ensure_ascii=False) + "\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ charla
    def _i_vacio(self, it):
        return Respuesta("No te escuché bien. Probá de nuevo.", sonido_error=True)

    def _i_no_entendi(self, it):
        return Respuesta("No entendí eso. Decí: qué podés hacer, y te cuento.", sonido_error=True)

    def _i_gracias(self, it):
        return random.choice(["De nada.", "Para eso estoy.", "Un placer."])

    def _i_hola(self, it):
        return random.choice(["Hola. ¿Qué necesitás?", "Acá estoy. ¿Qué hacemos?"])

    def _i_ayuda(self, it):
        return AYUDA

    def _i_si(self, it):
        return "¿Sí qué? No te había preguntado nada."

    def _i_no(self, it):
        return "Ok."

    # ------------------------------------------------------------------ hora y fecha
    def _i_hora(self, it):
        return f"Son las {tx.decir_hora(self.ahora())}."

    def _i_fecha(self, it):
        hoy = self.ahora().date()
        return f"Hoy es {tx.DIAS_SEMANA_TILDE[hoy.weekday()]} {hoy.day} de {tx.MESES[hoy.month - 1]}."

    # ------------------------------------------------------------------ timers y alarmas
    def _i_timer(self, it):
        seg = it.datos.get("segundos")
        if not seg:
            return Respuesta("¿De cuánto? Decí por ejemplo: timer de diez minutos.", sonido_error=True)
        etiqueta = it.datos.get("etiqueta") or ""
        self.agenda.agregar("timer", self.ahora() + timedelta(seconds=seg), etiqueta, duracion=seg)
        extra = f" para {etiqueta}" if etiqueta else ""
        return f"Timer de {tx.decir_duracion(seg)}{extra}, arrancando."

    def _i_cuanto_falta(self, it):
        timers = self.agenda.listar("timer")
        if not timers:
            return "No hay ningún timer andando."
        falta = int((timers[0].dt - self.ahora()).total_seconds())
        return f"Faltan {tx.decir_duracion(max(falta, 1))}."

    def _i_cancelar_timer(self, it):
        quitados = self.agenda.cancelar("timer", todos=it.datos.get("todos", False))
        if not quitados:
            return "No había timers."
        return "Timers cancelados." if len(quitados) > 1 else "Timer cancelado."

    def _i_alarma(self, it):
        ahora = self.ahora()
        c = tx.parsear_cuando(it.texto, ahora)
        cuando = tx.resolver_alarma(c, ahora)
        if cuando is None:
            return Respuesta("¿A qué hora? Decí por ejemplo: alarma a las siete.", sonido_error=True)
        self.agenda.agregar("alarma", cuando, "")
        return f"Alarma para {tx.decir_cuando(cuando, True, ahora)}. Va a sonar por el audio de la PC."

    def _i_listar_alarmas(self, it):
        alarmas = self.agenda.listar("alarma")
        if not alarmas:
            return "No tenés alarmas."
        ahora = self.ahora()
        partes = [tx.decir_cuando(a.dt, True, ahora) for a in alarmas[:4]]
        return "Tenés alarma " + ", y ".join(partes) + "."

    def _i_cancelar_alarma(self, it):
        quitados = self.agenda.cancelar("alarma", todos=it.datos.get("todos", False))
        if not quitados:
            return "No había alarmas."
        if len(quitados) > 1:
            return "Borré todas las alarmas."
        return f"Cancelé la alarma de {tx.decir_cuando(quitados[0].dt, True, self.ahora())}."

    # ------------------------------------------------------------------ recordatorios y calendario
    def _google_activo(self) -> bool:
        return bool(self.cfg.get("google", {}).get("activado"))

    def _i_recordatorio(self, it):
        ahora = self.ahora()
        t = it.texto
        t = re.sub(r"^(?:recordame|recordarme|recorda|recuerdame|acordame|haceme acordar|avisame)\s*(?:que\s+|de\s+)?", "", t)
        c = tx.parsear_cuando(t, ahora)
        inicio, tiene_hora = tx.resolver_evento(c, ahora)
        titulo = tx.limpiar_titulo(c.resto)
        if not titulo:
            return Respuesta("¿Qué te tengo que recordar?", sonido_error=True)
        if inicio is None:
            # sin fecha: queda como tarea
            if self._google_activo():
                gg.crear_tarea(titulo)
                return f"Anotado en tus tareas: {titulo}."
            return Respuesta("¿Para cuándo? Decí por ejemplo: recordame mañana a las cinco sacar la basura.", sonido_error=True)
        dicho = tx.decir_cuando(inicio, tiene_hora, ahora)
        if tiene_hora and isinstance(inicio, datetime):
            self.agenda.agregar("recordatorio", inicio, titulo)
        if self._google_activo():
            g = self.cfg["google"]
            if tiene_hora:
                gg.crear_evento(titulo, inicio, True, g.get("calendario", "primary"), aviso_minutos=0, duracion_min=15)
            else:
                gg.crear_tarea(titulo, inicio if isinstance(inicio, date) else inicio.date())
            return f"Listo, te lo recuerdo {dicho}: {titulo}. También te va a llegar al celular."
        if not tiene_hora:
            return Respuesta("Decime también la hora, así te aviso. Por ejemplo: mañana a las cinco.", sonido_error=True)
        return f"Listo, te aviso {dicho}: {titulo}."

    def _i_agregar_evento(self, it):
        ahora = self.ahora()
        t = it.texto
        t = re.sub(r"\b(?:al|a mi|en mi|en el|a la|en la)\s+(?:calendario|agenda)\b", " ", t)
        t = re.sub(r"^(?:anota|anote|anotar|anotame|agrega|agregue|agregar|agregame|suma|sumale|pone|pon|agenda|agendame|agendar)\s*(?:que\s+)?", "", t.strip())
        t = re.sub(r"\b(?:un|el) (?:evento|turno)\b(?: de| del| para)?", " ", t)
        c = tx.parsear_cuando(t, ahora)
        inicio, tiene_hora = tx.resolver_evento(c, ahora)
        titulo = tx.limpiar_titulo(c.resto)
        if not titulo:
            return Respuesta("¿Qué querés que agregue al calendario?", sonido_error=True)
        if inicio is None:
            return Respuesta(f"¿Para qué día es {titulo}?", sonido_error=True)
        if not self._google_activo():
            raise gg.GoogleNoConfigurado
        g = self.cfg["google"]
        gg.crear_evento(titulo, inicio, tiene_hora, g.get("calendario", "primary"), aviso_minutos=g.get("aviso_minutos", 30))
        return f"Agregué {titulo} al calendario, {tx.decir_cuando(inicio, tiene_hora, ahora)}."

    def _i_que_tengo(self, it):
        ahora = self.ahora()
        c = tx.parsear_cuando(it.texto, ahora)
        dia = c.fecha or ahora.date()
        dicho = tx.decir_dia(dia, ahora.date())
        partes = []
        if self._google_activo():
            g = self.cfg["google"]
            eventos = gg.eventos_del_dia(dia, g.get("calendario", "primary"))
            if eventos:
                items = [f"{t} a las {tx.decir_hora(h)}" if h else t for t, h in eventos[:5]]
                partes.append("En el calendario: " + ", ".join(items) + ".")
            tareas = [t for t, vence in gg.listar_tareas() if vence is not None and vence <= dia]
            if tareas:
                partes.append("Tareas para " + dicho + ": " + ", ".join(tareas[:5]) + ".")
        locales = [a for a in self.agenda.listar() if a.dt.date() == dia and a.tipo in ("alarma", "recordatorio")]
        for a in locales[:3]:
            if a.tipo == "alarma":
                partes.append(f"Alarma a las {tx.decir_hora(a.dt)}.")
            elif not self._google_activo():
                partes.append(f"Recordatorio a las {tx.decir_hora(a.dt)}: {a.texto}.")
        if not partes:
            if not self._google_activo():
                return f"No tengo nada anotado para {dicho}. Para ver tu calendario hay que conectar Google."
            return f"{dicho.capitalize()} no tenés nada anotado."
        return f"{dicho.capitalize()}: " + " ".join(partes)

    # ------------------------------------------------------------------ tareas
    def _i_agregar_tarea(self, it):
        titulo = tx.limpiar_titulo(it.datos.get("texto", ""))
        if not titulo:
            return Respuesta("¿Qué anoto?", sonido_error=True)
        if not self._google_activo():
            raise gg.GoogleNoConfigurado
        c = tx.parsear_cuando(titulo, self.ahora())
        vence = c.fecha
        if vence:
            titulo = tx.limpiar_titulo(c.resto) or titulo
        gg.crear_tarea(titulo, vence)
        extra = f", para {tx.decir_dia(vence, self.ahora().date())}" if vence else ""
        return f"Anotado: {titulo}{extra}."

    def _i_listar_tareas(self, it):
        if not self._google_activo():
            raise gg.GoogleNoConfigurado
        tareas = gg.listar_tareas()
        if not tareas:
            return "No tenés tareas pendientes. Bien ahí."
        nombres = [t for t, _ in tareas[:6]]
        extra = f" Y {len(tareas) - 6} más." if len(tareas) > 6 else ""
        return f"Tenés {len(tareas)} {'tarea' if len(tareas) == 1 else 'tareas'}: " + ", ".join(nombres) + "." + extra

    def _i_completar_tarea(self, it):
        if not self._google_activo():
            raise gg.GoogleNoConfigurado
        hecha = gg.completar_tarea(it.datos.get("texto", ""))
        if not hecha:
            return Respuesta("No encontré esa tarea en la lista.", sonido_error=True)
        return f"Tachada: {hecha}."

    # ------------------------------------------------------------------ clima
    def _i_clima(self, it):
        ciudad = self.cfg.get("ciudad", {})
        try:
            return clima.resumen(float(ciudad.get("lat", -34.44)), float(ciudad.get("lon", -58.56)),
                                 ciudad.get("nombre", "tu ciudad"), dia=it.datos.get("dia", 0))
        except Exception:  # noqa: BLE001
            log.exception("clima")
            return Respuesta("No pude consultar el clima. Fijate que haya internet.", sonido_error=True)

    # ------------------------------------------------------------------ luz
    def _i_luz(self, it):
        encender = it.datos.get("encender", True)
        luz.cambiar(self.cfg.get("luz", {}), encender, it.datos.get("brillo"))
        return "Luz prendida." if encender else "Luz apagada."

    # ------------------------------------------------------------------ PC
    def _i_suspender(self, it):
        def hacer():
            threading.Timer(2.5, pc.suspender).start()
            return "Suspendo la PC. Para despertarla, tocá una tecla o el mouse."
        return self._confirmar("¿Suspendo la PC? Decí sí o no.", hacer)

    def _i_apagar_pc(self, it):
        def hacer():
            pc.apagar(60)
            return "La PC se apaga en un minuto. Si te arrepentís, decí: cancelá el apagado."
        return self._confirmar("¿Apago la PC? Decí sí o no.", hacer)

    def _i_cancelar_apagado(self, it):
        return "Apagado cancelado." if pc.cancelar_apagado() else "No había ningún apagado programado."

    def _i_bloquear(self, it):
        threading.Timer(1.5, pc.bloquear).start()
        return "Bloqueo la PC."

    def _i_volumen_poner(self, it):
        p = pc.volumen_poner(it.datos.get("valor", 50))
        return f"Volumen al {p} por ciento."

    def _i_volumen_cambiar(self, it):
        p = pc.volumen_cambiar(it.datos.get("delta", 10))
        return f"Volumen al {p} por ciento." if p >= 0 else "Listo."

    def _i_silenciar(self, it):
        quedo = pc.silenciar(it.datos.get("valor"))
        return "Silencio." if quedo else "Sonido de vuelta."

    # ------------------------------------------------------------------ música y YouTube
    def _i_musica_play(self, it):
        return pc.musica_play()

    def _i_musica_pausa(self, it):
        return pc.musica_pausa()

    def _i_musica_siguiente(self, it):
        pc.musica_siguiente()
        return "Siguiente."

    def _i_musica_anterior(self, it):
        pc.musica_anterior()
        return "Anterior."

    def _i_youtube_play(self, it):
        consulta = it.datos.get("consulta", "").strip()
        titulo = pc.reproducir_youtube(consulta)
        if titulo is None:
            return f"No pude elegir un video, te abro la búsqueda de {consulta}."
        return f"Pongo {titulo}."

    def _i_youtube_music(self, it):
        consulta = it.datos.get("consulta", "").strip()
        titulo = pc.reproducir_youtube_music(consulta)
        if titulo is None:
            return f"Te abro YouTube Music con {consulta}."
        return f"Pongo {titulo} en YouTube Music. Después sigue con temas parecidos."

    def _i_spotify_buscar(self, it):
        consulta = it.datos.get("consulta", "").strip()
        try:
            pc.buscar_spotify(consulta)
        except OSError:
            return Respuesta("No encontré Spotify instalado.", sonido_error=True)
        return f"Abrí Spotify con {consulta}. Elegí qué poner."

    def _i_que_suena(self, it):
        return pc.que_suena() or "No sé qué está sonando."

    def _i_youtube(self, it):
        consulta = it.datos.get("consulta", "").strip()
        if not consulta:
            pc.abrir("https://www.youtube.com")
            return "Abro YouTube."
        pc.buscar_youtube(consulta)
        return f"Busco en YouTube: {consulta}."

    def _i_abrir(self, it):
        nombre = it.datos.get("app", "")
        encontrada = pc.buscar_app(nombre, self.cfg.get("apps", {}))
        if encontrada is None:
            return Respuesta(f"No tengo {nombre} en mi lista de apps. Se agrega en la configuración.", sonido_error=True)
        clave, destino = encontrada
        try:
            pc.abrir(destino)
        except OSError:
            return Respuesta(f"No pude abrir {clave}. Revisá la ruta en la configuración.", sonido_error=True)
        return f"Abro {clave}."

    # ------------------------------------------------------------------ modos y rutinas
    def _i_modo_juego(self, it):
        activar = it.datos.get("activar", True)
        self.cambiar_modo_juego(activar)
        if activar:
            return "Modo juego activado. Solo te escucho con la tecla."
        return "Modo juego desactivado. Ya me podés decir Hey Jarvis."

    def _i_buenas_noches(self, it):
        hechos = []
        try:
            if pc._sesion_medios() is not None:  # noqa: SLF001
                pc.musica_pausa()
                hechos.append("pausé la música")
        except Exception:  # noqa: BLE001
            pass
        try:
            luz.cambiar(self.cfg.get("luz", {}), False)
            hechos.append("apagué la luz")
        except Exception:  # noqa: BLE001
            pass
        ahora = self.ahora()
        manana = (ahora + timedelta(days=1)).date()
        alarmas = [a for a in self.agenda.listar("alarma") if a.dt.date() in (ahora.date(), manana)]
        frase = "Buenas noches."
        if hechos:
            frase += " " + " y ".join(hechos).capitalize() + "."
        if alarmas:
            frase += f" Tu alarma suena {tx.decir_cuando(alarmas[0].dt, True, ahora)}."

        def hacer():
            threading.Timer(2.5, pc.suspender).start()
            return "Que descanses."
        return self._confirmar(frase + " ¿Suspendo la PC?", hacer)


def frase_aviso(a: Aviso, ahora: datetime) -> str:
    if a.tipo == "timer":
        return f"Terminó el timer para {a.texto}." if a.texto else f"Terminó el timer de {tx.decir_duracion(a.duracion)}."
    if a.tipo == "alarma":
        return f"Son las {tx.decir_hora(ahora)}. Arriba."
    return f"Te recuerdo: {a.texto}."


__all__ = ["Nucleo", "Respuesta", "frase_aviso", "preparar"]

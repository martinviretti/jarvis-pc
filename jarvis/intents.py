"""Del texto que dijo a una orden concreta. Reglas en rioplatense, sin IA, fáciles de probar."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .texto import normalizar, parsear_duracion

# Errores típicos de la transcripción -> lo que se quiso decir
CORRECCIONES = [
    (r"\b(?:yo tuve|you tube|yutub|yutu|iutub|lu tube|yu tub|youtub|you tub)\b", "youtube"),
    (r"\b(?:espotify|spoti|spotifai|spotifay)\b", "spotify"),
    (r"\b(?:chat gpt|chat g p t|chatyipiti|chat yipiti|chat jipiti|chatgipiti|chat gepete)\b", "chatgpt"),
    (r"\b(?:taimer|tiemer|time|tymer|taymer)\b", "timer"),
    (r"^(?:de acuerda|recuerda me|recorda me|recordar me|record me|recordame que|acuerda me|acuerdame|recuerdame|recordami)\b", "recordame"),
    (r"^tapa la luz\b", "apaga la luz"),
    (r"^(?:paga|pagá|apagar) la luz\b", "apaga la luz"),
    (r"\bla pc\b|\bla pece\b|\bla compu\b|\bla computadora\b|\bel ordenador\b|\bla maquina\b", "la pc"),
]


@dataclass
class Intent:
    nombre: str
    datos: dict = field(default_factory=dict)
    texto: str = ""


def preparar(texto: str) -> str:
    t = normalizar(texto)
    for patron, reemplazo in CORRECCIONES:
        t = re.sub(patron, reemplazo, t)
    return re.sub(r"\s+", " ", t).strip()


def _hay(t: str, patron: str) -> re.Match | None:
    return re.search(patron, t)


# verbos en voseo, tuteo, usted e infinitivo (sin tildes)
V_PONER = r"(?:pone|pon|ponga|poneme|ponme|pongas|poner|programa|programame|arma|armame|hace|haceme|crea|creame|activa|configura|seteame|setea)"
V_APAGAR = r"(?:apaga|apague|apagar|apagame|apagala|corta|cortala)"
V_PRENDER = r"(?:prende|prenda|prender|prendeme|prendela|encende|enciende|encienda|encender|enciendeme|encendela)"
V_ABRIR = r"(?:abri|abre|abra|abrir|abrime|abrime|ejecuta|inicia|lanza|arranca|arrancame|entra a|anda a|abrilo)"
V_ANOTAR = r"(?:anota|anote|anotar|anotame|agrega|agregue|agregar|agregame|suma|sumale|sumame|mete|pone|pon)"
V_CANCELAR = r"(?:cancela|cancelar|cancelame|borra|borrar|saca|quita|elimina|frena|detene|apaga|para (?:el|la) (?:timer|temporizador|alarma))"


def interpretar(texto_original: str) -> Intent:
    t = preparar(texto_original)
    I = lambda n, **d: Intent(n, d, t)  # noqa: E731

    if not t:
        return I("vacio")

    # ---- cortesía y ayuda
    if _hay(t, r"^(?:gracias|muchas gracias|genial gracias|buenisimo|joya|de 10|perfecto)\b"):
        return I("gracias")
    if _hay(t, r"\b(?:que (?:podes|sabes|puedes) hacer|que haces|ayuda|que comandos|que te puedo pedir|como (?:te uso|funcionas))\b"):
        return I("ayuda")
    if _hay(t, r"^(?:hola|buenas|buen dia|buenos dias|buenas tardes)\b(?! noches)") and len(t.split()) <= 3:
        return I("hola")

    # ---- confirmaciones sueltas (las usa el núcleo cuando pregunta "¿sí o no?")
    if _hay(t, r"^(?:si|sii+|dale|ok|okay|okey|de una|confirmo|hacelo|obvio|claro|si dale|afirmativo)\b"):
        return I("si")
    if _hay(t, r"^(?:no|nop|nah|no no|deja|dejalo|mejor no|no gracias|cancela|cancelar|para)$|^no\b(?! (?:la )?apagues)"):
        return I("no")

    # ---- modo juego
    if _hay(t, r"\b(?:desactiva|desactivar|saca|sali del|salir del|termina|apaga|apagar)\b.*\bmodo juego\b") or _hay(t, r"\bmodo normal\b"):
        return I("modo_juego", activar=False)
    if _hay(t, r"\bmodo (?:juego|gamer|gaming)\b"):
        return I("modo_juego", activar=True)

    # ---- rutina buenas noches
    if _hay(t, r"\b(?:buenas noches|me voy a dormir|a dormir|hora de dormir)\b") and not _hay(t, r"\bpc\b"):
        return I("buenas_noches")

    # ---- hora y fecha
    if _hay(t, r"\bque hora (?:es|son)\b|\bhora es\b|\bme decis la hora\b|^la hora$"):
        return I("hora")
    if _hay(t, r"\bque (?:dia|fecha) (?:es|estamos)\b|\ba que (?:dia|fecha) estamos\b|\bque dia es hoy\b"):
        return I("fecha")

    # ---- luz (antes que "apagá la pc")
    if _hay(t, r"\bluz\b|\bluces\b|\blampara\b|\bvelador\b"):
        if _hay(t, rf"\b{V_APAGAR}\b"):
            return I("luz", encender=False)
        if _hay(t, rf"\b{V_PRENDER}\b|\bda(?:me)? luz\b"):
            m = _hay(t, r"\bal (\d{1,3})\s*(?:%|por ciento)?\b")
            return I("luz", encender=True, brillo=int(m[1]) if m else None)

    # ---- PC: cancelar apagado, apagar, suspender, bloquear
    if _hay(t, rf"\b{V_CANCELAR}\b.*\bapagado\b|\bno (?:la )?apagues\b"):
        return I("cancelar_apagado")
    if _hay(t, rf"\b(?:suspende|suspender|suspendela|suspendeme|suspende la|pone a dormir|mandala a dormir|dormi)\b.*\bpc\b|\bsuspende(?:r)?\b(?!.*\b(?:timer|alarma)\b)"):
        return I("suspender")
    if _hay(t, rf"\b{V_APAGAR}\b.*\bpc\b|\bapagate\b"):
        return I("apagar_pc")
    if _hay(t, r"\bbloquea(?:r)?\b.*\b(?:pc|pantalla)\b"):
        return I("bloquear")

    # ---- timers
    if _hay(t, r"\b(?:timer|temporizador|cronometro|cuenta regresiva)\b") or _hay(t, r"\bavisame en\b|\bavisame dentro de\b"):
        if _hay(t, rf"\b{V_CANCELAR}\b"):
            return I("cancelar_timer", todos=bool(_hay(t, r"\btodos\b")))
        if _hay(t, r"\bcuanto (?:falta|queda)\b"):
            return I("cuanto_falta")
        seg, resto = parsear_duracion(t)
        return I("timer", segundos=seg, etiqueta=_etiqueta_timer(resto))
    if _hay(t, r"\bcuanto (?:falta|queda)\b"):
        return I("cuanto_falta")

    # ---- alarmas
    if _hay(t, r"\balarmas?\b|\bdespertame\b|\bdespertador\b"):
        if _hay(t, rf"\b{V_CANCELAR}\b|\bno quiero\b"):
            return I("cancelar_alarma", todos=bool(_hay(t, r"\btodas\b")))
        if _hay(t, r"\bque alarmas\b|\btengo alarmas?\b|\bhay alarmas?\b|\ba que hora (?:es|esta) la alarma\b"):
            return I("listar_alarmas")
        return I("alarma")

    # ---- recordatorios (van al calendario con aviso, y Jarvis también avisa si la PC está prendida)
    if _hay(t, r"^(?:recordame|recordarme|recorda|recuerdame|acordame|haceme acordar|avisame)\b"):
        return I("recordatorio")

    # ---- calendario: consultar
    if _hay(t, r"\bque (?:tengo|hay)\b(?! anotado)(?! en (?:la )?lista)(?! en (?:mis )?tareas)") or _hay(t, r"\b(?:mi|la) agenda\b.*\b(?:hoy|manana)\b|\btengo algo\b"):
        return I("que_tengo")
    if _hay(t, r"\bcalendario\b|\bagenda\b|\bevento\b|\bturno\b"):
        if _hay(t, rf"\b{V_ANOTAR}\b|\bagenda(?:me|r)?\b"):
            return I("agregar_evento")
        return I("que_tengo")
    if _hay(t, r"^agenda(?:me|r)?\b"):
        return I("agregar_evento")

    # ---- tareas
    if _hay(t, r"\bque (?:tengo|hay) (?:anotado|en (?:la )?lista|en (?:mis )?tareas|pendiente)\b|\b(?:leeme|decime|cuales son) (?:las|mis) tareas\b|\bmis tareas\b$|\bque tareas tengo\b"):
        return I("listar_tareas")
    m = _hay(t, r"^(?:tacha|tachar|tachame|completa|completar|marca(?:r)? como hecha|ya hice|ya termine|termine|borra(?:r)? de la lista|borra(?:r)? la tarea)\s+(?:la tarea\s+)?(.+)$")
    if m:
        return I("completar_tarea", texto=m[1].strip())
    m = _hay(t, rf"^{V_ANOTAR}\s+(.+?)\s+(?:a|en)\s+(?:la lista|las tareas|mis tareas|tareas|la lista de tareas|pendientes)$")
    if m:
        return I("agregar_tarea", texto=m[1].strip())
    m = _hay(t, r"^(?:anota|anotame|anotar|anote|agrega una tarea|nueva tarea|tarea)\s+(?:que\s+)?(.+)$")
    if m:
        return I("agregar_tarea", texto=m[1].strip())

    # ---- clima
    if _hay(t, r"\b(?:clima|tiempo hace|que tiempo|temperatura|llover|llueve|lluvia|paraguas|hace frio|hace calor|cuantos grados|pronostico)\b"):
        return I("clima", dia=1 if _hay(t, r"\bmanana\b") else 0)

    # ---- volumen
    m = _hay(t, r"\bvolumen (?:al|en|a)\s+(\d{1,3})\b|\b(?:pone|pon|deja) (?:el )?volumen (?:al|en|a)\s+(\d{1,3})\b")
    if m:
        return I("volumen_poner", valor=int(m[1] or m[2]))
    if _hay(t, r"\b(?:subi|sube|subir|subile|subime|mas)\b.*\b(?:volumen|sonido|audio)\b|\bmas fuerte\b|\bvolumen arriba\b"):
        return I("volumen_cambiar", delta=20 if _hay(t, r"\bmucho\b") else 10)
    if _hay(t, r"\b(?:baja|bajar|bajale|bajame|menos)\b.*\b(?:volumen|sonido|audio)\b|\bmas (?:bajo|despacio)\b|\bvolumen abajo\b"):
        return I("volumen_cambiar", delta=-20 if _hay(t, r"\bmucho\b") else -10)
    if _hay(t, r"\b(?:saca|quita|quitar|sacar) (?:el )?(?:silencio|mute)\b|\bdesmutea(?:r)?\b|\bactiva el sonido\b"):
        return I("silenciar", valor=False)
    if _hay(t, r"^(?:silencio|mute|mutea|mutear|silencia|silenciar|silencia el sonido|callate todo)$|\b(?:silencia|mutea)(?:r)? (?:el )?(?:sonido|audio|volumen|la pc)\b"):
        return I("silenciar", valor=True)

    # ---- YouTube
    m = _hay(t, r"\b(?:busca|buscame|buscar|buscan|busque|pone|pon|poneme|mostrame|abri)\s+(?:en\s+)?(?:el\s+)?youtube\s+(.+)$") or \
        _hay(t, r"\b(?:busca|buscame|buscar|pone|poneme)\s+(.+?)\s+en\s+youtube$") or \
        _hay(t, r"^youtube\s+(.+)$")
    if m:
        consulta = re.sub(r"^(?:a |el |la |que |de |sobre )", "", m[1].strip())
        return I("youtube", consulta=consulta)

    # ---- música
    if _hay(t, r"\bque (?:tema|cancion|musica) (?:es|esta sonando|suena)\b|\bque esta sonando\b"):
        return I("que_suena")
    if _hay(t, r"\b(?:siguiente|proximo|proxima|pasa|pasala|saltea|salta|cambia)\b.*\b(?:tema|cancion)\b|^(?:siguiente|proximo tema|otro tema|next)$"):
        return I("musica_siguiente")
    if _hay(t, r"\b(?:anterior|volve al|tema anterior|cancion anterior)\b"):
        return I("musica_anterior")
    if _hay(t, r"\b(?:pausa|pausar|pausala|pausa la|para la musica|frena la musica|deten|detene la musica|stop|corta la musica)\b"):
        return I("musica_pausa")
    if _hay(t, rf"\b{V_PONER}\b.*\b(?:musica|spotify|un tema|temas|play)\b|^(?:play|reproduci|segui|continua|despausa|reanuda)\b|\b(?:segui|continua|reanuda) (?:la )?musica\b"):
        return I("musica_play")

    # ---- abrir apps
    m = _hay(t, rf"^{V_ABRIR}\s+(?:el |la |los |las |un |una |al )?(.+)$")
    if m:
        return I("abrir", app=m[1].strip())

    return I("no_entendi")


def _etiqueta_timer(resto: str) -> str:
    """'pone un timer de para los fideos' -> 'los fideos'."""
    m = re.search(r"\bpara (.+)$", resto)
    if m and not re.search(r"\b(?:timer|temporizador)\b", m[1]):
        return m[1].strip()
    return ""

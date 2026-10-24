"""Tour guiado del pitch: reproduce la corrida demo con un tope de hora y pausa en cada hito de pasos.py.

El recuadro y el spotlight son un componente propio (index.html + tour.js + tour.css, sin npm ni CDN) que se dibuja
sobre la página. El componente manda eventos (siguiente, anterior, salir, tick…); aquí se avanza el tope
(st.session_state.repro) y hub.db oculta todo lo posterior (db.fijar_tope).
"""
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from dashboard.tour.pasos import PASOS
from hub import db
from hub import tiempo as T
from hub.config import cargar

_componente = components.declare_component("tour", path=str(Path(__file__).resolve().parent))
CLAVE = "tour_ui"


def _cfg() -> dict:
    """Parámetros del tour (config/default.yaml · dashboard.tour)."""
    return cargar()["dashboard"]["tour"]


def reloj(hora: float) -> str:
    """'Día 2 · 23:00' (días contados desde 1, como en config/demo.yaml)."""
    return f"Día {T.dia(hora) + 1} · {T.hhmm(hora)}"


# ── reproducción (también fuera del tour: play / pausa / en vivo) ────────────
def repro_activa(corrida: str) -> bool:
    """True si la corrida se está reproduciendo con tope."""
    r = st.session_state.get("repro")
    return bool(r) and r["corrida"] == corrida


def play_pausa() -> None:
    """Alterna play y pausa de la reproducción."""
    r = st.session_state.repro
    r["play"], r["t"] = not r["play"], time.time()


def en_vivo() -> None:
    """Quita el tope: vuelve a mostrar todo lo escrito en la base."""
    st.session_state.repro = None
    st.session_state.corrida_tour = None


def _avanzar_play() -> None:
    """Play normal: horas_por_segundo_play desde el último tick, sin pasar de lo escrito."""
    r = st.session_state.repro
    ahora = time.time()
    real = db.ahora_real(r["corrida"])
    r["tope"] = min(real, r["tope"] + (ahora - r.get("t", ahora)) * _cfg()["horas_por_segundo_play"])
    r["t"] = ahora
    if r["tope"] >= real:
        r["play"] = False


# ── ciclo del tour ───────────────────────────────────────────────────────────
def iniciar(paso: int = 0) -> None:
    """Arranca el tour desde la hora 0 de la corrida demo; con paso > 0 salta hasta el hito anterior a ese paso."""
    ss = st.session_state
    cid = _cfg()["corrida"]
    if cid not in set(db.corridas()["corrida_id"]):
        ss.tour = {"error": f"No está la corrida «{cid}» en {db.ruta_base()}. Créala con "
                            "python -m sim.run_vivo --velocidad 0 y vuelve a abrir el tour."}
        return
    ss.corrida_tour = cid
    ss.repro = {"corrida": cid, "tope": 0.0, "play": False}
    ss.tour = {"paso": 0, "buscando": False, "objetivo": None, "horas": {}, "error": None}
    ss.criticas_vistas, ss.primera, ss.abiertas, ss.inc_sel = set(), True, set(), None
    paso = max(0, min(int(paso), len(PASOS) - 1))
    for j in range(paso):
        if PASOS[j].hito:
            h = PASOS[j].hito(cid, ss.repro["tope"])
            if h is not None:
                ss.repro["tope"] = h
        ss.tour["horas"][j] = ss.repro["tope"]
    _ir_a(paso)


def _accion(i: int) -> None:
    """Corre la acción del paso; si pide otra corrida (sin red), la muestra sin tope."""
    ss, p = st.session_state, PASOS[i]
    cid = _cfg()["corrida"]
    if ss.corrida_tour != cid:              # volvemos de la corrida sin red
        ss.corrida_tour, ss.repro = cid, ss.tour["repro_demo"]
    if not p.accion:
        return
    db.fijar_tope(ss.repro["tope"])
    otra = p.accion(cid)
    if otra and otra != cid:
        ss.tour["repro_demo"] = ss.repro
        ss.corrida_tour, ss.repro = otra, None


def _ir_a(i: int) -> None:
    """Entra al paso i: abre su pantalla y, si su hito no ha ocurrido, avanza la simulación hasta él."""
    ss = st.session_state
    t, r = ss.tour, ss.repro
    t.update(paso=i, buscando=False, objetivo=None)
    _accion(i)
    p = PASOS[i]
    if i in t["horas"] or not p.hito or ss.repro is None:
        _llegar()
        return
    ahora = time.time()
    t.update(buscando=True, objetivo=p.hito(r["corrida"], r["tope"]), h0=r["tope"], t0=ahora,
             real=db.ahora_real(r["corrida"]), t_real=ahora)


def _llegar() -> None:
    """El hito ocurrió: el paso se muestra con la simulación en pausa."""
    ss = st.session_state
    t = ss.tour
    t["buscando"] = False
    if ss.repro is not None:
        t["horas"].setdefault(t["paso"], ss.repro["tope"])
        ss.repro["play"] = False
    _accion(t["paso"])                      # otra vez: la alerta o incidencia del hito ya es visible


def _avanzar_busqueda() -> None:
    """Tick: avanza el tope a ms_por_hora hacia el hito; sin hito escrito, espera datos nuevos o se rinde."""
    ss, cfg = st.session_state, _cfg()
    t, r = ss.tour, ss.repro
    ahora = time.time()
    h = t["h0"] + (ahora - t["t0"]) * 1000 / cfg["ms_por_hora"]
    if t["objetivo"] is None:
        t["objetivo"] = PASOS[t["paso"]].hito(r["corrida"], r["tope"])
    real = db.ahora_real(r["corrida"])
    if real > t["real"]:
        t["real"], t["t_real"] = real, ahora
    if t["objetivo"] is not None and h >= t["objetivo"]:
        r["tope"] = t["objetivo"]
        _llegar()
        return
    r["tope"] = min(h, real)
    if t["objetivo"] is None and h >= real and ahora - t["t_real"] > cfg["espera_vivo_s"]:
        _llegar()                           # el hito no está en la base: el paso se muestra igual


def salir() -> None:
    """Cierra el tour: la simulación queda en pausa donde iba, con play / pausa / en vivo en la barra."""
    ss = st.session_state
    t = ss.tour or {}
    if t.get("repro_demo") and ss.corrida_tour != _cfg()["corrida"]:
        ss.corrida_tour, ss.repro = _cfg()["corrida"], t["repro_demo"]
    if ss.get("repro"):
        ss.repro["play"] = False
    ss.tour, ss.mapa_capa, ss.cama = None, None, None


def _procesar(ev: dict) -> bool:
    """Aplica un evento del componente; True si hay que rearmar toda la página."""
    ss = st.session_state
    a, t = ev.get("accion"), ss.get("tour")
    if a == "iniciar":
        if ev.get("auto") and ss.tour_auto:
            return False
        ss.tour_auto = True
        iniciar()
        return True
    if a == "repetir":
        iniciar()
        return True
    if a == "salir":
        salir()
        return True
    if a == "tick":
        if t and not t.get("error") and t["buscando"]:
            _avanzar_busqueda()
            return not t["buscando"]
        if not t and ss.get("repro") and ss.repro["play"]:
            _avanzar_play()
        return False
    if not t or t.get("error"):
        return False
    if a == "siguiente" and not t["buscando"]:
        if t["paso"] >= len(PASOS) - 1:
            salir()
        else:
            _ir_a(t["paso"] + 1)
        return True
    if a == "anterior" and not t["buscando"] and t["paso"] > 0:
        t["paso"] -= 1
        _accion(t["paso"])
        return True
    return False


def _al_cambiar() -> None:
    """Callback del componente: guarda el evento para procesarlo en el cuerpo del fragmento."""
    st.session_state.tour_evento = st.session_state.get(CLAVE)


def desde_url() -> None:
    """?tour=1 fuerza el tour, ?tour=0 lo apaga, ?paso=N arranca en el paso N (una vez por sesión)."""
    ss = st.session_state
    if ss.tour_auto:
        return
    q = st.query_params
    if q.get("tour") == "0":
        ss.tour_auto = True
    elif "paso" in q or q.get("tour") == "1":
        ss.tour_auto = True
        try:
            n = int(q.get("paso", "1"))
        except ValueError:
            n = 1
        iniciar(n - 1)


def componente() -> None:
    """Procesa el último evento del recuadro y lo dibuja con el estado actual (va al inicio del fragmento principal)."""
    ss, cfg = st.session_state, _cfg()
    ev = ss.pop("tour_evento", None)
    if ev and ev.get("n") != ss.get("tour_ult_n"):
        ss.tour_ult_n = ev.get("n")
        if _procesar(ev):
            st.rerun(scope="app")
    t, r = ss.get("tour"), ss.get("repro")
    args = {"activo": bool(t), "auto": not ss.tour_auto and st.query_params.get("tour") != "0",
            "espera_ms": cfg["espera_target_ms"], "total": len(PASOS), "tick_ms": 0}
    if t and t.get("error"):
        args.update(error=t["error"], paso=0)
    elif t:
        i, p = t["paso"], PASOS[t["paso"]]
        args.update(paso=i, id=p.id, titulo=p.titulo, texto=p.texto, target=p.target, cerca=p.cerca,
                    permitir=p.permitir_interaccion, buscando=t["buscando"],
                    reloj=reloj(r["tope"]) if r else "", tick_ms=cfg["ms_por_hora"] if t["buscando"] else 0)
    elif r and r["play"]:
        args["tick_ms"] = int(1000 / cfg["horas_por_segundo_play"])
    args["eco"] = ss.get("tour_ult_n")      # cambia con cada evento: el componente se vuelve a dibujar y pide el siguiente tick
    with st.container(key="tour_comp"):
        _componente(**args, key=CLAVE, default=None, on_change=_al_cambiar)

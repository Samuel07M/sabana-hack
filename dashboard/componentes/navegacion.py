"""Menú lateral (pantallas, contadores y estado de red) y barra superior (título, reloj, tema y campana)."""
import streamlit as st

from dashboard import tour
from dashboard.componentes.estado import Ctx, avisar, ir_a
from dashboard.componentes.ui import css_icono, estilo, html, ic, ico_box
from hub import alertas as A
from hub import celular, db
from hub import tiempo as T

TABS = [("finca", "map", "Panorama"), ("alertas", "bell", "Alertas"), ("incidencias", "clip", "Incidencias"),
        ("ventilacion", "wind", "Ventilación"), ("analisis", "chart", "Análisis")]
TITULOS = {
    "finca": ("Panorama de la finca", "Riesgo a 7 días, robots e incidencias por bloque"),
    "alertas": ("Alertas", "Posible enfermedad y enfermedad confirmada"),
    "incidencias": ("Incidencias", "Trazabilidad de hallazgos, tratamientos, revisitas y ventilación"),
    "ventilacion": ("Ventilación", "Control por nave para frenar el transporte de esporas"),
    "analisis": ("Análisis", "Desempeño del sistema en la temporada"),
}
CSS_REPRO = (".st-key-boton_tour button,.st-key-repro_play button,.st-key-repro_vivo button{height:40px;border-radius:12px!important;"
             "background:var(--card)!important;border:1px solid var(--border)!important;color:var(--muted)!important;"
             "box-shadow:var(--shadow);font-weight:600}"
             ".st-key-boton_tour button:hover,.st-key-repro_play button:hover,.st-key-repro_vivo button:hover"
             "{color:var(--text)!important;border-color:var(--border-2)!important}")
MARCA = ('<div class="brand"><svg width="36" height="36" viewBox="0 0 36 36"><defs><linearGradient id="lg1" x1="0" y1="0" '
         'x2="1" y2="1"><stop offset="0" stop-color="#6E7BFF"/><stop offset="1" stop-color="#A57BFF"/></linearGradient></defs>'
         '<rect width="36" height="36" rx="11" fill="url(#lg1)"/><circle cx="14" cy="20" r="7" fill="#fff" opacity=".92"/>'
         '<circle cx="22" cy="15" r="6" fill="#fff" opacity=".6"/><path d="M12.5 17.5l1.5 1 1.5-1" stroke="#6E7BFF" '
         'stroke-width="1.4" fill="none" stroke-linecap="round"/></svg><div><div class="name">Berry Good Idea</div>'
         '<div class="sub">Monitoreo de Botrytis</div></div></div>')


def _css_nav(tab: str, n_alertas: int, hot: bool, n_inc: int) -> str:
    """Íconos, pantalla activa y contadores del menú (CSS generado en cada refresco)."""
    css = "".join(css_icono(f"nav_{k}", i, 19) for k, i, _ in TABS)
    css += (f".st-key-nav_{tab} button{{background:var(--accent-soft)!important;color:var(--text)!important}}"
            f".st-key-nav_{tab} button::before{{background:var(--accent)!important}}"
            f".st-key-nav_{tab} button p{{font-weight:600!important}}")
    for k, n in (("alertas", n_alertas), ("incidencias", n_inc)):
        if n:
            css += f'.st-key-nav_{k} button::after{{content:"{n}"}}'
        else:
            css += f".st-key-nav_{k} button::after{{display:none}}"
    for k, _, _ in TABS:
        if k not in ("alertas", "incidencias"):
            css += f".st-key-nav_{k} button::after{{display:none}}"
    if hot:
        css += (".st-key-nav_alertas button::after{background:color-mix(in srgb,var(--crit) 20%,transparent)!important;"
                "color:var(--crit)!important}")
    return css


def lateral(corrida: str) -> None:
    """Contenido del menú lateral (se llama dentro de un fragmento con refresco)."""
    nuevas = A.de_pantalla(corrida, estado="nueva")
    hot = bool((nuevas["severidad"] == "critica").any())
    n_inc = len(db.incidencias(corrida, grupo="abiertas"))
    estilo(_css_nav(st.session_state.tab, len(nuevas), hot, n_inc))
    with st.container(key="brand"):
        html(MARCA)
    with st.container(key="nav"):
        html('<div class="nav-t">Monitoreo</div>')
        for k, _, t in TABS:
            if st.button(t, key=f"nav_{k}", width="stretch"):
                ir_a(k)
                st.rerun()
    with st.container(key="pie"):
        if db.red(corrida) == "local":
            html(f'<div class="side-foot"><div class="row" style="gap:10px">{ico_box("radio", "var(--ok)", True, 16)}<div>'
                 '<div style="font-weight:650;font-size:13px">Hub local en línea</div>'
                 '<div class="tiny muted">Datos en tiempo real</div></div></div></div>')
            return
        pend = len(db.cola_pendiente(corrida))
        html(f'<div class="side-foot"><div class="row" style="gap:10px">{ico_box("phone", "var(--adv)", True, 16)}<div>'
             '<div style="font-weight:650;font-size:13px">Sin red</div>'
             f'<div class="tiny muted">{pend} datos en los robots</div></div></div></div>')
        if st.button("Pasa el celular", key="celular", type="primary", width="stretch"):
            n = celular.sincronizar(corrida)
            avisar("Celular sincronizado", f"{n} datos descargados de los robots", ":material/smartphone:")
            st.rerun()


def barra_superior(ctx: Ctx) -> None:
    """Título de la pantalla, reloj simulado, botón de tema y campana."""
    titulo, sub = TITULOS[st.session_state.tab]
    nuevas = len(A.de_pantalla(ctx.corrida, estado="nueva"))
    if nuevas:
        estilo('.st-key-campana button::after{content:"";position:absolute;top:8px;right:9px;width:8px;height:8px;'
               'border-radius:50%;background:var(--crit);box-shadow:0 0 0 2px var(--card)}')
    with st.container(key="top", horizontal=True, vertical_alignment="center", gap="medium"):
        html(f'<div class="top"><h1>{titulo}</h1><div class="sub">{sub}</div></div>', width="stretch")
        html(f'<div class="clock">{ic('clock', 18)}<div><div class="t">{T.hhmm(ctx.ahora)}</div>'
             f'<div class="d">{T.fecha_larga(ctx.ahora, ctx.ini)}</div></div></div>', width="content")
        _controles_tour(ctx)
        if st.button("Cambiar tema", key="boton_tema", help="Cambiar tema"):
            st.session_state.tema = "light" if st.session_state.tema == "dark" else "dark"
            st.rerun()
        if st.button("Alertas", key="campana", help="Alertas"):
            ir_a("alertas")
            st.rerun()



def _controles_tour(ctx: Ctx) -> None:
    """Botón ▶ Tour y, si la corrida se reproduce con tope fuera del tour, play / pausa y volver a en vivo."""
    estilo(CSS_REPRO)
    ss = st.session_state
    if tour.repro_activa(ctx.corrida) and not ss.tour:
        play = ss.repro["play"]
        if st.button("❚❚ Pausa" if play else "▶ Play", key="repro_play", help="Pausar o seguir la reproducción de la corrida"):
            tour.play_pausa()
            st.rerun()
        if st.button("● En vivo", key="repro_vivo", help="Mostrar todo lo escrito en la base"):
            tour.en_vivo()
            st.rerun()
    if st.button("▶ Tour", key="boton_tour", help="Tour guiado (reinicia la corrida demo desde la hora 0)"):
        ss.tour_auto = True
        tour.iniciar()
        st.rerun()

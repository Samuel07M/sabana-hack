"""Pantalla Alertas (riesgo_7d y confirmacion en dos columnas) y la tarjeta de alerta que también usa Trazabilidad."""
import streamlit as st

from dashboard.componentes.estado import Ctx, abrir_cama, avisar, ir_a
from dashboard.componentes.ui import LABEL, SEV_V, TIPO_IC, chip, clicable, esc, estilo, html, ic, ico_box, mascara, nulo
from hub import alertas as A
from hub import tiempo as T

ESTADOS = [("todas", "Todas"), ("nueva", "Nuevas"), ("vista", "Vistas"), ("resuelta", "Resueltas")]
COLUMNAS = [("confirmacion", "Enfermedad confirmada", "Enfermedad confirmada por la inspección del robot", "octagon",
             "var(--crit)"),
            ("riesgo_7d", "Posible enfermedad", "Camas con riesgo alto de infección en los próximos 7 días", "trend",
             "var(--adv)")]
CSS = (
    "".join(f'[class*="st-key-acard_n_{s}"]{{border-color:color-mix(in srgb,{v} 35%,var(--border))!important}}'
            for s, v in SEV_V.items())
    + '[class*="st-key-vercama_"] button::before,[class*="st-key-verinc_"] button::before,.st-key-a_incidencias button::before'
      '{content:"";width:15px;height:15px;flex:none;background:currentColor}'
)


def _iconos_enlaces() -> str:
    """Íconos de 'Ver cama', 'Ver incidencia' y del enlace a Incidencias."""
    m, c = mascara("map"), mascara("clip")
    return (f'[class*="st-key-vercama_"] button::before{{-webkit-mask:{m} center/contain no-repeat;mask:{m} center/contain no-repeat}}'
            f'[class*="st-key-verinc_"] button::before,.st-key-a_incidencias button::before'
            f'{{-webkit-mask:{c} center/contain no-repeat;mask:{c} center/contain no-repeat}}')


def estilos() -> None:
    """CSS de las tarjetas de alerta."""
    estilo(CSS + _iconos_enlaces())


def tarjeta(a: dict, ctx: Ctx, pref: str) -> None:
    """Tarjeta que se expande: al abrirla pasa a 'vista'; dentro, mensaje, acciones y enlaces."""
    aid = int(a["alerta_id"])
    abierta = aid in st.session_state.abiertas
    nueva = a["estado"] == "nueva"
    color = SEV_V[a["severidad"]]
    acc = A.acciones(a["tipo"])
    if a["estado"] == "resuelta":
        lado = chip(LABEL["accion"].get(a["accion"], a["accion"] or ""), "c-ok", False)
    else:
        lado = chip(LABEL["sev"][a["severidad"]], "c-" + a["severidad"])
    clave = f"acard_{'n' if nueva else 'v'}_{a['severidad']}_{pref}_{aid}"
    with st.container(key=clave):
        cab = (f'<div class="acard-h" data-tour="alerta-{esc(a["tipo"])}-{esc(a["cama_id"])}">{ico_box(TIPO_IC[a["tipo"]], color, False, 18)}<div style="flex:1;min-width:0">'
               f'<div class="row" style="gap:8px;flex-wrap:nowrap">{f"<span class=newdot style=--c:{color}></span>" if nueva else ""}'
               f'<span class="tt" style="min-width:0">{esc(a["titulo"])}</span></div>'
               f'<div class="meta">{esc(LABEL["tipo"][a["tipo"]])} · {T.etiqueta(a["hora"], ctx.ini)}</div></div>'
               f'{lado}<span class="chev {"open" if abierta else ""}">{ic("chev", 18)}</span></div>')
        if clicable(f"ah_{pref}_{aid}", cab):
            if abierta:
                st.session_state.abiertas.discard(aid)
            else:
                st.session_state.abiertas.add(aid)
                A.marcar_vista(aid)
            st.rerun()
        if not abierta:
            return
        with st.container(key=f"ab_{pref}_{aid}"):
            html(f'<p class="msg">{esc(a["mensaje"])}</p>')
            with st.container(key=f"acc_{pref}_{aid}", horizontal=True, vertical_alignment="center"):
                if a["estado"] != "resuelta":
                    for i, x in enumerate(acc):
                        if st.button(LABEL["accion"].get(x, x), key=f"res_{pref}_{aid}_{x}",
                                     type="primary" if i == 0 else "secondary"):
                            if A.resolver(aid, x):
                                avisar("Alerta resuelta", LABEL["accion"].get(x, x))
                                st.session_state.abiertas.discard(aid)
                            st.rerun()
                st.space("stretch")
                if a["cama_id"] and st.button("Ver cama", key=f"vercama_{pref}_{aid}", type="tertiary"):
                    ir_a("finca")
                    abrir_cama(a["cama_id"])
                    st.rerun()
                if not nulo(a["incidencia_id"]) and st.button(
                        "Ver incidencia", key=f"verinc_{pref}_{aid}", type="tertiary"):
                    ir_a("incidencias")
                    st.session_state.inc_filtro = "todas"
                    st.session_state.inc_sel = int(a["incidencia_id"])
                    st.rerun()


def segmento(clave: str, opciones: list[tuple], valor: str) -> str | None:
    """Botones segmentados (.seg del prototipo); devuelve la opción pulsada."""
    elegido = None
    with st.container(key=f"seg_{clave}", horizontal=True, gap=None):
        for v, t in opciones:
            if st.button(t, key=f"sg_{clave}_{v}", type="primary" if v == valor else "secondary"):
                elegido = v
    return elegido


def pantalla(ctx: Ctx) -> None:
    """Alertas: filtros y dos columnas, confirmada y posible enfermedad."""
    estilos()
    ss, g = st.session_state, ctx.cfg["geometria"]
    with st.container(key="card_filtros", horizontal=True, vertical_alignment="center"):
        e = segmento("estado", ESTADOS, ss.f_estado)
        if e:
            ss.f_estado = e
            st.rerun()
        opts = ["todos"] + [str(b) for b in range(1, g["bloques"] + 1)]
        bl = st.selectbox("Bloque", opts, index=opts.index(ss.f_bloque), key="sel_bloque", label_visibility="collapsed",
                          format_func=lambda v: "Todos los bloques" if v == "todos" else f"Bloque {v}", width=180)
        if bl != ss.f_bloque:
            ss.f_bloque = bl
            st.rerun()
        st.space("stretch")
        if st.button("Seguimientos y ventilación en Incidencias", key="a_incidencias", type="tertiary"):
            ir_a("incidencias")
            st.rerun()
    maxl = ctx.cfg["dashboard"]["ui"]["max_alertas_lista"]
    todas = A.de_pantalla(ctx.corrida, bloque=ss.f_bloque)
    with st.container(key="acols"):
        cols = st.columns(2, gap="medium")
        for (tipo, titulo, sub, icono, color), col in zip(COLUMNAS, cols):
            with col:
                al = A.de_pantalla(ctx.corrida, tipo=tipo, estado=ss.f_estado, bloque=ss.f_bloque)
                n = int(((todas["tipo"] == tipo) & (todas["estado"] == "nueva")).sum())
                html(f'<div class="acol-hd" style="--c:{color}">{ico_box(icono, color, False, 20)}<div style="flex:1;min-width:0">'
                     f'<h3>{titulo}</h3><div class="sub">{sub}</div></div><div class="acol-n"><div class="v num">{len(al)}</div>'
                     f'<div class="tiny muted">{f"<b style=color:{color}>{n}</b> sin revisar" if n else "al día"}</div></div></div>')
                if al.empty:
                    html(f'<div class="card empty">{ico_box(icono, color)}<div>Sin alertas con estos filtros.</div></div>')
                    continue
                for a in al.head(maxl).to_dict("records"):
                    tarjeta(a, ctx, "al")
                if len(al) > maxl:
                    html(f'<div class="small muted">Mostrando {maxl} de {len(al)}</div>')

"""Pantalla Incidencias: embudo, tabla con filtros, CSV, línea de tiempo y Trazabilidad."""
import streamlit as st

from dashboard.componentes import alertas as AL
from dashboard.componentes.estado import Ctx, abrir_cama, ir_a
from dashboard.componentes.graficas import timeline_inc
from dashboard.componentes.ui import C_INC, LABEL, V_INC, chip, clicable, css_icono, esc, estilo, f2, html, ico_box, mascara, nulo, plural
from hub import alertas as A
from hub import db
from hub import tiempo as T
from hub import ubicacion as U

GRUPOS = [("abiertas", "Abiertas"), ("todas", "Todas"), ("cerradas", "Cerradas"), ("descartadas", "Descartadas")]
COLS_CSV = ["incidencia_id", "cama_id", "ubicacion", "posicion", "origen", "estado", "hora_creada", "hora_confirmada",
            "hora_cerrada", "confianza", "plantas_afectadas"]


def csv(ctx: Ctx) -> bytes:
    """CSV de todas las incidencias (con BOM para Excel en Windows)."""
    df = db.incidencias(ctx.corrida).copy()
    df["ubicacion"] = df["cama_id"].map(U.legible)
    for c in ("hora_creada", "hora_confirmada", "hora_cerrada", "posicion", "plantas_afectadas"):
        df[c] = df[c].astype("Int64")
    return ("﻿" + df[COLS_CSV].to_csv(index=False, lineterminator="\r\n")).encode("utf-8")


def _tabla(ctx: Ctx, lista) -> None:
    """Tabla de incidencias con filas que se pueden clicar."""
    sel = st.session_state.inc_sel
    with st.container(height=min(540, 42 + 48 * len(lista)), key="tblwrap", border=False):
        html('<div class="trow th"><span>#</span><span>Ubicación</span><span>Pos.</span><span>Origen</span><span>Estado</span>'
             '<span>Conf.</span><span>Plantas</span><span>Creada</span></div>')
        for i in lista.to_dict("records"):
            iid = int(i["incidencia_id"])
            fila = (f'<div class="trow {"sel" if sel == iid else ""}"><span class="muted">{iid}</span>'
                    f'<span style="font-weight:600">{esc(U.corto(i["cama_id"]))}</span>'
                    f'<span>{"—" if nulo(i["posicion"]) else int(i["posicion"])}</span><span>{LABEL["origen"][i["origen"]]}</span>'
                    f'<span>{chip(LABEL["inc"][i["estado"]], C_INC[i["estado"]])}</span><span>{f2(i["confianza"])}</span>'
                    f'<span>{"—" if nulo(i["plantas_afectadas"]) else int(i["plantas_afectadas"])}</span>'
                    f'<span class="muted">{T.etiqueta(i["hora_creada"], ctx.ini)}</span></div>')
            if clicable(f"trow_{iid}", fila):
                st.session_state.inc_sel = iid
                st.rerun()


def _detalle(ctx: Ctx, todas) -> None:
    """Línea de tiempo de la incidencia seleccionada."""
    sel = st.session_state.inc_sel
    fila = todas[todas["incidencia_id"] == sel] if sel is not None else todas.iloc[0:0]
    if fila.empty:
        html(f'<div class="empty">{ico_box("clip", "var(--accent)")}<div>Selecciona una incidencia para ver su historial.</div></div>')
        return
    i = fila.iloc[0].to_dict()
    segs = db.seguimientos(ctx.corrida, int(i["incidencia_id"]))
    html(f'<div class="card-hd"><div><div class="h3">Incidencia #{int(i["incidencia_id"])}</div><div class="sub">'
         f'{esc(U.legible(i["cama_id"]))} · posición {int(i["posicion"])}</div></div><div class="spacer"></div>'
         f'{chip(LABEL["inc"][i["estado"]], C_INC[i["estado"]])}</div>'
         + timeline_inc(i, segs, ctx.cfg["drones"]["horas_hasta_tratamiento"], ctx.ini))
    with st.container(horizontal=True, vertical_alignment="center", key="det_pie"):
        if st.button("Ver cama", key="det_cama"):
            ir_a("finca")
            abrir_cama(i["cama_id"])
            st.rerun()
        html(f'<span class="small muted">El dron registra cada revisita cada {ctx.cfg["drones"]["dias_revisita"]} días.</span>',
             width="content")


def trazabilidad(ctx: Ctx) -> None:
    """Alertas de seguimiento, ventilación y descartada, con filtro por tipo y contadores."""
    ss = st.session_state
    maxl = ctx.cfg["dashboard"]["ui"]["max_alertas_lista"]
    with st.container(key="card_traza"):
        with st.container(horizontal=True, vertical_alignment="center", key="traza_hd"):
            html('<div><div class="h3">Trazabilidad</div><div class="sub">Revisitas del dron, cambios de ventilación y '
                 'sospechas descartadas</div></div>', width="content")
            st.space("stretch")
            todos = A.de_trazabilidad(ctx.corrida)
            opciones = [("todos", f"Todo {len(todos)}")] + [
                (k, f"{LABEL['tipo'][k]} {int((todos['tipo'] == k).sum())}") for k in A.TIPOS_TRAZA]
            t = AL.segmento("traza", opciones, ss.traza)
            if t:
                ss.traza = t
                st.rerun()
        ev = A.de_trazabilidad(ctx.corrida, ss.traza)
        if ev.empty:
            html(f'<div class="empty">{ico_box("repeat", "var(--accent)")}<div>Sin eventos registrados todavía.</div></div>')
            return
        for a in ev.head(maxl).to_dict("records"):
            AL.tarjeta(a, ctx, "tz")
        if len(ev) > maxl:
            html(f'<div class="small muted" style="margin-top:10px">Mostrando {maxl} de {len(ev)}</div>')


def pantalla(ctx: Ctx) -> None:
    """Incidencias."""
    AL.estilos()
    ss = st.session_state
    estilo(css_icono("det_cama", "map", 15) + f'.st-key-csv{{margin-left:auto}}.st-key-csv button::before{{content:"";width:15px;height:15px;flex:none;'
           f'background:currentColor;-webkit-mask:{mascara("download")} center/contain no-repeat;'
           f'mask:{mascara("download")} center/contain no-repeat}}')
    todas = db.incidencias(ctx.corrida)
    estados = list(LABEL["inc"])
    html(f'<div class="card"><div class="card-hd"><div><h3>Ciclo de las incidencias</h3><div class="sub">'
         f'{plural(len(todas), "incidencia registrada", "incidencias registradas")} en la temporada</div></div></div>'
         '<div class="pipe">' + "".join(
             f'<div class="pipe-i" style="--c:{V_INC[e]}"><div class="n">{int((todas["estado"] == e).sum())}</div>'
             f'<div class="l">{LABEL["inc"][e]}</div></div>' for e in estados) + '</div></div>')
    with st.container(key="incs"):
        izq, der = st.columns([1.45, 1], gap="medium")
        with izq, st.container(key="card_tabla"):
            with st.container(horizontal=True, vertical_alignment="center"):
                g = AL.segmento("inc", GRUPOS, ss.inc_filtro)
                if g:
                    ss.inc_filtro = g
                    st.rerun()
                st.download_button("Exportar CSV", csv(ctx), key="csv", mime="text/csv", on_click="ignore",
                                   file_name=f"incidencias_{ctx.corrida}_{T.corta(ctx.ahora, ctx.ini).replace(' ', '-')}.csv")
            lista = db.incidencias(ctx.corrida, grupo=ss.inc_filtro)
            if lista.empty:
                html(f'<div class="empty">{ico_box("leaf", "var(--ok)")}<div>Sin incidencias en este grupo.</div></div>')
            else:
                _tabla(ctx, lista)
        with der, st.container(key="card_det"):
            _detalle(ctx, todas)
    trazabilidad(ctx)

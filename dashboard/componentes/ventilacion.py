"""Pantalla Ventilación: estado por nave (sin interruptores: es automática), cuándo apagarla e historial."""
import streamlit as st

from dashboard.componentes.estado import Ctx
from dashboard.componentes.ui import esc, html, ico_box, nulo
from hub import db
from hub import tiempo as T


def pantalla(ctx: Ctx) -> None:
    """Ventilación por nave en cada bloque."""
    v = db.ventilacion_actual(ctx.corrida)
    hist = db.ventilacion_historial(ctx.corrida)
    horas = ctx.cfg["robots"]["horas_ventilacion_apagada"]
    naves = sorted(set(int(n) for n in v["nave"]))
    bloques = ""
    for b in sorted(set(int(x) for x in v["bloque"])):
        cards = ""
        for r in v[v["bloque"] == b].itertuples():
            on = r.estado == "encendida"
            motivo = "Sin cambios desde el inicio" if nulo(r.motivo) else f"{esc(r.motivo)} · {T.hace(r.hora, ctx.ahora)}"
            cards += (f'<div class="vcard" data-tour="vent-B{b}-N{int(r.nave)}"><div><div style="font-weight:650">Nave {int(r.nave)}</div>'
                      f'<div class="tiny" style="color:{"var(--ok)" if on else "var(--adv)"};font-weight:600">'
                      f'{"Encendida" if on else "Apagada"}</div></div><div class="tiny muted">{motivo}</div></div>')
        bloques += f'<div><div class="sec" style="margin-top:4px">Bloque {b}</div><div class="vgrid">{cards}</div></div>'
    if hist.empty:
        tl = '<div class="small muted">Sin cambios todavía.</div>'
    else:
        tl = '<div class="tl">' + "".join(
            f'<div class="ev" style="--c:var(--{"ok" if r.estado == "encendida" else "adv"})"><div class="h">'
            f'{T.etiqueta(r.hora, ctx.ini)}</div><div class="t">B{int(r.bloque)} · Nave {int(r.nave)} · {r.estado}</div>'
            f'<div class="small muted">{esc(r.motivo)}</div></div>' for r in hist.itertuples()) + "</div>"
    with st.container(key="vent"):
        izq, der = st.columns([1, 0.36], gap="medium")
        with izq:
            html(f'<div class="card stack" style="gap:14px"><div class="card-hd" style="margin:0"><div><h3>Ventilación por nave</h3>'
                 f'<div class="sub">Naves con ventilación controlable: {", ".join(map(str, naves))}</div></div></div>{bloques}</div>')
        with der:
            html(f'<div class="stack"><div class="card"><div class="card-hd">{ico_box("wind", "var(--info)", True, 16)}'
                 '<h3>Cuándo apagarla</h3></div><div class="small" style="display:flex;flex-direction:column;gap:10px">'
                 '<div class="factor" style="align-items:flex-start"><span class="chip c-ok">Encendida</span><span class="muted">'
                 'Baja la humedad de la nave, pero el aire lleva esporas a las camas siguientes.</span></div>'
                 '<div class="factor" style="align-items:flex-start"><span class="chip c-advertencia">Apagada</span>'
                 '<span class="muted">Frena el transporte de esporas, pero sube la humedad, sobre todo en los bordes.</span></div>'
                 f'<div class="muted">Se apaga {horas} h de forma automática cuando se confirma Botrytis en la nave. '
                 'Se vuelve a encender sola al terminar.</div></div></div>'
                 f'<div class="card"><div class="card-hd"><h3>Historial</h3></div>{tl}</div></div>')

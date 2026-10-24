"""Detalle de cama: st.dialog como panel lateral derecho, igual que el drawer del prototipo."""
import streamlit as st

from dashboard.componentes.estado import Ctx, cerrar_cama, contexto
from dashboard.componentes.graficas import gauge, grafica_clima, grafica_riesgo, timeline_inc
from dashboard.componentes.ui import (ABIERTA, C_INC, LABEL, chip, color_riesgo, f1, f2, html, ic, ico_box, nulo, pct,
                                      plural)
from hub import db
from hub import enfermedades as E
from hub import tiempo as T
from hub import ubicacion as U


def _factores(v: dict, umbral: float, horas_reglas: float, enfermedad: str) -> list[tuple]:
    """Filas de "Qué explica este riesgo" (misma lógica del prototipo)."""
    dist, edad = int(v["dist"]), v["edad"]
    delta = v["delta_hr"] or 0.0
    fac = [
        ("drop", "var(--alto)" if v["wet72"] >= horas_reglas else "var(--info)",
         f"Humedad ≥ {umbral:g} % durante <b>{int(v['wet72'])} h</b> en 72 h · <b>{int(v['wet24'])} h</b> en 24 h"),
        ("thermo", "var(--adv)", f"Temperatura media 24 h <b>{f1(v['t_mean'])} °C</b>"
         + ("" if nulo(v["hr_max24"]) else f" · humedad máxima <b>{f1(v['hr_max24'])} %</b>")),
        ("activity", "var(--accent)", f"Cambio de humedad frente al día anterior <b>{'+' if delta >= 0 else ''}{f1(delta)} %</b>"),
        ("octagon", "var(--crit)" if dist < 99 else "var(--ok)",
         f"<b>{enfermedad} confirmada en esta cama</b>" if dist == 0 else
         f"{enfermedad} confirmada a <b>{plural(dist, 'cama', 'camas')}</b> en la misma nave" if dist < 99 else
         "Sin casos confirmados en la nave"),
        ("robot", "var(--insp)", "Aún sin medición directa del robot: se usa el sensor del bloque" if nulo(edad) else
         f"Última medición directa del robot <b>hace {int(edad)} h</b>"),
    ]
    if v["borde"]:
        fac.append(("edge", "var(--muted)", "Cama de borde: suele acumular más humedad"))
    return fac


def contenido(ctx: Ctx, cid: str) -> str:
    """HTML completo del detalle de una cama."""
    cfg, h = ctx.cfg, ctx.ahora
    b, n, c = U.partes(cid)
    serie = db.riesgo_cama(ctx.corrida, cid)
    r = serie.iloc[-1] if len(serie) else None
    v = db.variables_cama(ctx.corrida, cid).iloc[0].to_dict()
    niv = r["nivel"] if r is not None else "sindato"
    vis = db.ultima_visita(ctx.corrida, cid)
    incs = db.incidencias(ctx.corrida, cama_id=cid)
    horas = cfg["dashboard"]["ui"]["horas_grafica"]
    lec = db.lecturas_cama(ctx.corrida, cid, h - horas, h)
    lc, sensor = lec[lec["serie"] == "cama"], lec[lec["serie"] == "sensor"]
    um = cfg["mojado"]["umbral_hr"]
    col = color_riesgo(r["prob_ia_7d"]) if r is not None else "var(--faint)"
    fac = _factores(v, um, cfg["dashboard"]["mock"]["modelo_prueba"]["umbral_mojado_reglas_h"], E.de_cama(cid))
    abiertas = "".join(chip(LABEL["inc"][e], C_INC[e]) for e in incs["estado"] if ABIERTA(e))
    dias = cfg["dashboard"]["ui"]["dias_riesgo"]
    tl = "".join(
        f'<div class="stat" style="margin-bottom:10px;padding:14px"><div class="row" style="margin-bottom:12px">'
        f'<b>#{int(i["incidencia_id"])}</b>{chip(LABEL["inc"][i["estado"]], C_INC[i["estado"]])}'
        f'<span class="small muted">posición {int(i["posicion"])}</span></div>'
        f'{timeline_inc(i, db.seguimientos(ctx.corrida, int(i["incidencia_id"])), cfg["robots"]["horas_hasta_tratamiento"], ctx.ini)}</div>'
        for i in incs.to_dict("records"))
    return (
        f'<div class="drawer"><div><div class="small muted">Bloque {b} · Nave {n}</div><div class="drawer-t">Cama {c}</div></div>'
        f'<div class="row" style="margin-top:12px;gap:6px">{chip("Riesgo " + LABEL["nivel"][niv].lower(), "c-" + niv)}'
        f'{chip("Cama de borde", "c-mute", False) if v["borde"] else ""}{abiertas}</div>'
        f'<div class="gauge-card" data-tour="riesgo"><div class="gauge">{gauge(None if r is None else r["prob_ia_7d"], col)}'
        f'<div class="v num" style="color:{col}">{pct(r["prob_ia_7d"]) if r is not None else "—"}</div>'
        f'<div class="l">Probabilidad de infección en 7 días</div></div><div class="stack" style="gap:12px">'
        f'<div class="stat"><div class="l">{ic("leaf", 13)}Riesgo por reglas</div><div class="v">'
        f'{f2(r["riesgo_reglas"]) if r is not None else "—"}</div></div>'
        f'<div class="stat"><div class="l">{ic("robot", 13)}Última visita</div><div class="v" style="font-size:14px">'
        f'{T.hace(vis["hora"].iloc[0], h) if len(vis) else "—"}</div></div></div></div>'
        f'<div class="sec">Qué explica este riesgo</div><div class="factores">'
        + "".join(f'<div class="factor">{ico_box(i, cc, True, 16)}<span>{t}</span></div>' for i, cc, t in fac)
        + f'</div><div class="sec">Humedad relativa · últimas {horas} h</div>'
        + grafica_clima(lc, sensor, "hr", h, horas, ctx.ini, vmin=50, vmax=100, umbral=um, unidad="%", color="var(--info)")
        + f'<div class="sec">Temperatura · últimas {horas} h</div>'
        + grafica_clima(lc, sensor, "temp_c", h, horas, ctx.ini, vmin=5, vmax=30, unidad="°C", color="var(--adv)")
        + '<div class="leyenda"><span><i style="background:var(--muted)"></i>Sensor del bloque</span><span><i style="'
          'background:var(--accent);height:8px;width:8px;border-radius:50%"></i>Medición del robot en la cama</span>'
          '<span><i style="background:var(--alto)"></i>Umbral de mojado</span></div>'
        + f'<div class="sec">Riesgo · últimos {dias} días</div>'
        + grafica_riesgo(serie.tail(dias), cfg["riesgo"]["umbral_alto"], cfg["riesgo"]["umbral_medio"], ctx.ini)
        + '<div class="sec">Incidencias</div>'
        + (tl or '<div class="small muted">Sin incidencias registradas en esta cama.</div>')
        + "</div>")


def abrir(corrida: str) -> None:
    """Abre el panel lateral de la cama seleccionada (se refresca solo mientras está abierto)."""
    cid = st.session_state.cama
    refresco = contexto(corrida).cfg["dashboard"]["refresco_s"]

    def cuerpo():
        @st.fragment(run_every=refresco)
        def vivo():
            if st.session_state.cama != cid:
                return
            html(contenido(contexto(corrida), cid))
        vivo()

    st.dialog(" ", position="right", width="large", on_dismiss=cerrar_cama)(cuerpo)()

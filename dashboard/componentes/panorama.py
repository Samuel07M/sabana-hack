"""Pantalla Panorama: KPIs, mapa 3D del bloque, robot, camas a vigilar y los 4 bloques (sin recuadros)."""
import streamlit as st

from dashboard.componentes.estado import Ctx, abrir_cama
from dashboard.componentes.graficas import sparkline
from dashboard.componentes.mapa3d import layout as LY
from dashboard.componentes.mapa3d import mapa3d
from dashboard.componentes.ui import (ABIERTA, C_ROBOT, LABEL, V_ROBOT, chip, clicable, color_riesgo, esc,
                                      f1, html, ic, ico_box, nulo, pct, plural)
from hub import db
from hub import tiempo as T
from hub import ubicacion as U


def kpis(ctx: Ctx) -> None:
    """Los 4 KPIs del prototipo, con sparkline y delta contra ayer en camas en riesgo alto."""
    h, al, inc = ctx.ahora, db.alertas(ctx.corrida), db.incidencias(ctx.corrida)
    crit = int(((al["severidad"] == "critica") & (al["estado"] == "nueva")).sum())
    crit24 = int(((al["severidad"] == "critica") & (al["hora"] > h - 24)).sum())
    abiertas = int(inc["estado"].map(ABIERTA).sum()) if len(inc) else 0
    nuevas24 = int((inc["hora_creada"] > h - 24).sum())
    serie = db.serie_riesgo(ctx.corrida)
    alto = int(serie["alto"].iloc[-1]) if len(serie) else 0
    delta = int(serie["alto"].iloc[-1] - serie["alto"].iloc[-2]) if len(serie) > 1 else None
    v = db.ventilacion_actual(ctx.corrida)
    off = int((v["estado"] == "apagada").sum())
    k = [
        ("alert", "var(--crit)", crit, "Alertas críticas sin revisar", f"<b>{crit24}</b> en las últimas 24 h", ""),
        ("clip", "var(--adv)", abiertas, "Incidencias abiertas", f"<b>{nuevas24}</b> nuevas en 24 h", ""),
        ("trend", "var(--alto)", alto, "Camas en riesgo alto",
         "Cálculo diario a las 06:00" if delta is None else f"<b>{'+' if delta >= 0 else ''}{delta}</b> frente a ayer",
         sparkline([int(x) for x in serie["alto"].tail(10)], "var(--alto)")),
        ("wind", "var(--info)", off, "Naves con ventilación apagada", f"de <b>{len(v)}</b> naves controlables", ""),
    ]
    html('<section class="kpis">' + "".join(
        f'<div class="kpi"><div class="row between">{ico_box(i, c, True, 17)}{sp}</div><div><div class="v">{val}</div>'
        f'<div class="l">{l}</div></div><div class="d">{d}</div></div>' for i, c, val, l, d, sp in k) + "</section>")


def _marcas_incidencia(ctx: Ctx, b: int) -> list[dict]:
    """Incidencias abiertas del bloque en la planta de su posición (centro de la cama si no la trae)."""
    marcas = []
    for i in db.incidencias(ctx.corrida, bloque=b, grupo="abiertas").itertuples():
        _, n, c = U.partes(i.cama_id)
        xy = LY.punto_robot(b, n, c, ctx.cfg) if nulo(i.posicion) else LY.punto_planta(b, n, c, int(i.posicion), ctx.cfg)
        marcas.append({"cama_id": i.cama_id, "xy": xy})
    return marcas


def _datos_mapa(ctx: Ctx, b: int, riesgo, dia) -> dict:
    """Datos del bloque para el componente mapa3d (riesgo, humedad, temperatura, tooltip, robot, incidencias y ventilación)."""
    cfg = ctx.cfg
    g = cfg["geometria"]
    clima = {r.cama_id: r for r in db.clima_bloque(ctx.corrida, b).itertuples()}
    vars_ = {r.cama_id: r for r in db.variables_bloque(ctx.corrida, b).itertuples()}
    rm = {r.cama_id: r for r in riesgo.itertuples()}
    camas, tips = [], {}
    for c in db.camas(b).itertuples():
        r, cl, v = rm.get(c.cama_id), clima.get(c.cama_id), vars_.get(c.cama_id)
        camas.append({"id": c.cama_id, "num": int(c.cama), "n": int(c.nave),
                      "mitades": LY.mitades_cama(b, int(c.nave), int(c.cama), cfg),
                      "prob": None if r is None else float(r.prob_ia_7d), "hr": None if cl is None else float(cl.hr),
                      "t": None if cl is None else float(cl.temp_c)})
        tips[c.cama_id] = {
            "nombre": U.sin_bloque(c.cama_id),
            "riesgo": f"{pct(r.prob_ia_7d)} · {LABEL['nivel'][r.nivel]}" if r is not None else "—",
            "color": color_riesgo(r.prob_ia_7d) if r is not None else "",
            "mojado": f"{int(v.wet72)} h" if v is not None else "—",
            "clima": f"{cl.temp_c:g} °C · {cl.hr:g} %" if cl is not None else "—",
            "medicion": (("Sensor del bloque" if cl.fuente == "sensor_fijo" else "Robot") + " · " + T.hace(cl.hora, ctx.ahora))
            if cl is not None else "—",
        }
    vent = {int(r.nave): r.estado for r in db.ventilacion_actual(ctx.corrida).itertuples() if r.bloque == b}
    dr = db.robots_actual(ctx.corrida)
    dr = dr[dr["robot_id"] == f"B{b}"]
    hc = cfg["riesgo"]["hora_calculo"]
    robot = None
    if not dr.empty:
        d = dr.iloc[0]
        _, n, c = U.partes(d["cama_id"])
        robot = {"robot_id": d["robot_id"], "cama_id": d["cama_id"], "estado": d["estado"], "xy": LY.punto_robot(b, n, c, cfg)}
    naves = range(1, g["naves_por_bloque"] + 1)
    return {
        "tema": st.session_state.tema, "bloque": b, "mapa": cfg["dashboard"]["mapa"], "camas": camas, "tips": tips,
        "dims": LY.dimensiones(b, cfg), "pasillo": LY.rect_pasillo(b, cfg),
        "naves": [{"n": n, "placas": LY.placas_nave(b, n, cfg), "flecha": LY.flecha_aire(b, n, cfg),
                   "etiqueta": LY.punto_etiqueta(b, n, cfg), "vent": vent.get(n)} for n in naves],
        "incidencias": _marcas_incidencia(ctx, b),
        "sel": st.session_state.cama, "capa": st.session_state.mapa_capa, "robot": robot,
        "titulo": f"Bloque {b}",
        "sub": "Esperando el primer cálculo de riesgo (06:00)" if dia is None else
               f"{g['naves_por_bloque']} naves · {g['naves_por_bloque'] * g['camas_por_nave']} camas · riesgo calculado el "
               f"{T.corta(dia * 24, ctx.ini)} a las {hc:02d}:00",
    }


def _bloques(ctx: Ctx, riesgo) -> None:
    """Los bloques como mini mapas de calor; punto rojo si tienen críticas nuevas."""
    g = ctx.cfg["geometria"]
    crit = db.alertas(ctx.corrida, severidad="critica", estado="nueva")
    crit_b = {U.bloque_de(x) for x in crit["cama_id"].dropna()}
    inc_ab = db.incidencias(ctx.corrida, grupo="abiertas")
    rm = {r.cama_id: r for r in riesgo.itertuples()}
    with st.container(key="bloques"):
        cols = st.columns(g["bloques"], gap="large")
        for b, col in zip(range(1, g["bloques"] + 1), cols):
            altos, cells = 0, ""
            for n in range(1, g["naves_por_bloque"] + 1):
                for k in range(1, g["camas_por_nave"] + 1):
                    r = rm.get(U.cama_id(b, n, (n - 1) * g["camas_por_nave"] + k))
                    altos += int(r is not None and r.nivel == "alto")
                    cells += f'<i style="background:{color_riesgo(r.prob_ia_7d) if r is not None else "var(--card-3)"}"></i>'
            ninc = int(inc_ab["cama_id"].str.startswith(f"B{b}-").sum()) if len(inc_ab) else 0
            on = "on" if st.session_state.bloque == b else ""
            if clicable(f"bcard_{b}", f'<div class="bcard {on}"><div class="row between"><b>Bloque {b}</b>'
                        f'{"<span class=alarm></span>" if b in crit_b else ""}</div><div class="mini">{cells}</div>'
                        f'<div class="bmeta"><span>{altos} en riesgo alto</span><span>{plural(ninc, "incidencia", "incidencias")}'
                        '</span></div></div>', dest=col):
                st.session_state.bloque = b
                st.rerun()


def bateria_pct(v) -> int:
    """Batería en % (0–100): el simulador escribe fracción 0–1 y el mock porcentaje."""
    v = float(v)
    return int(round(max(0.0, min(100.0, v * 100 if v <= 1 else v))))


def _tarjeta_robot(ctx: Ctx, b: int) -> None:
    """Estado, ubicación, T, HR, batería y cola de prioridad del robot del bloque."""
    dr = db.robots_actual(ctx.corrida)
    dr = dr[dr["robot_id"] == f"B{b}"]
    if dr.empty:
        html('<div class="pano"><div class="h3">Robot</div><div class="small muted">Sin datos del robot.</div></div>')
        return
    d = dr.iloc[0]
    pulso = "pulse" if d["estado"] == "inspeccionando" else ""
    html(f'<div class="card-hd" style="margin-bottom:16px;flex-wrap:nowrap">{ico_box("robot", V_ROBOT[d["estado"]], False, 20)}<div>'
         f'<div class="h3">Robot {esc(d["robot_id"])}</div><div class="sub">'
         f'{"Última posición conocida" if ctx.sin_red else "Cámara 360 · sensores de clima"}</div></div>'
         f'<div class="spacer"></div>{chip(LABEL["robot"][d["estado"]], C_ROBOT[d["estado"]], True, pulso)}</div>')
    extra = " · " + T.hace(d["hora"], ctx.ahora) if ctx.sin_red else ""
    if clicable("dpos", f'<div class="robot-pos"><div class="tiny muted">Ubicación</div><div class="v">'
                f'{esc(U.sin_bloque(d["cama_id"]))}</div><div class="tiny faint">{T.etiqueta(d["hora"], ctx.ini)}{extra}</div></div>'):
        abrir_cama(d["cama_id"])
        st.rerun()
    cl = db.clima_actual(ctx.corrida, d["cama_id"])
    t = f'{f1(cl["temp_c"].iloc[0])} °C' if len(cl) else "—"
    hr = f'{f1(cl["hr"].iloc[0])} %' if len(cl) else "—"
    bat = bateria_pct(d["bateria"])
    bc = "var(--ok)" if bat > 50 else "var(--adv)" if bat > 25 else "var(--crit)"
    html(f'<div class="pano"><div class="stats2"><div class="stat"><div class="l">{ic("thermo", 13)}Temperatura</div>'
         f'<div class="v">{t}</div></div><div class="stat"><div class="l">{ic("drop", 13)}Humedad</div><div class="v">{hr}</div>'
         f'</div></div><div class="row between" style="margin:14px 0 6px"><span class="small muted" '
         f'style="display:flex;gap:6px;align-items:center">{ic("battery", 14)}Batería</span><b class="num">{bat} %</b></div>'
         f'<div class="bar" style="--c:{bc}"><i style="width:{bat}%"></i></div><div class="sec">Cola de prioridad</div></div>')
    pri = db.prioridades_robot(ctx.corrida, d["robot_id"])
    if pri.empty:
        html('<span class="small muted">Patrulla rutinaria por todas las camas del bloque.</span>')
        return
    with st.container(key="chips", horizontal=True):
        for cid in pri["cama_id"]:
            if st.button(U.sin_bloque(cid), key=f"chip_{cid}"):
                abrir_cama(cid)
                st.rerun()


def _camas_a_vigilar(ctx: Ctx, b: int, riesgo) -> None:
    """Top de camas en riesgo alto y medio del bloque."""
    rb = riesgo[riesgo["cama_id"].str.startswith(f"B{b}-")] if len(riesgo) else riesgo
    altos = rb[rb["nivel"] == "alto"].sort_values("prob_ia_7d", ascending=False) if len(rb) else rb
    medios = rb[rb["nivel"] == "medio"].sort_values("prob_ia_7d", ascending=False) if len(rb) else rb
    rank = list(altos.itertuples()) + list(medios.itertuples())
    rank = rank[:ctx.cfg["dashboard"]["ui"]["top_camas"]]
    html(f'<div style="margin:36px 0 8px"><div class="h3">Camas a vigilar</div><div class="sub">'
         f'{plural(len(altos), "cama", "camas")} en riesgo alto en el bloque</div></div>')
    if not rank:
        html('<div class="small muted" style="padding:8px 0">Sin camas en riesgo medio o alto.</div>')
        return
    for r in rank:
        if clicable(f"rank_{r.cama_id}", f'<div class="rank-i"><span class="small" style="font-weight:600">'
                    f'{esc(U.sin_bloque(r.cama_id))}</span><div class="bar" style="--c:{color_riesgo(r.prob_ia_7d)}">'
                    f'<i style="width:{r.prob_ia_7d * 100}%"></i></div><span class="p">{pct(r.prob_ia_7d)}</span></div>'):
            abrir_cama(r.cama_id)
            st.rerun()


def pantalla(ctx: Ctx) -> None:
    """Panorama de la finca."""
    b = st.session_state.bloque
    kpis(ctx)
    riesgo = db.riesgo_ultimo(ctx.corrida)
    dia = int(riesgo["dia"].iloc[0]) if len(riesgo) else None
    with st.container(key="finca"):
        izq, der = st.columns([1, 0.38], gap="large")
        with izq:
            with st.container(key="tour_mapa"):
                clic = mapa3d(_datos_mapa(ctx, b, riesgo, dia), key="mapa3d")
            if clic and clic.get("t") != st.session_state.ult_click:
                st.session_state.ult_click = clic.get("t")
                abrir_cama(clic["cama"])
                st.rerun()
            _bloques(ctx, riesgo)
        with der:
            with st.container(key="pano_side"):
                with st.container(key="tour_robot"):
                    _tarjeta_robot(ctx, b)
                _camas_a_vigilar(ctx, b, riesgo)

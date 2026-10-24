"""Gráficas SVG del prototipo (sin librerías ni internet): sparkline, medidor, clima, riesgo, área, dona y línea de tiempo."""
import math

import pandas as pd

from dashboard.componentes.ui import LABEL, RAMPA_RIESGO, V_RES, esc, f2, nulo, pct, plural, rampa, rgb
from hub import tiempo as T


def sparkline(vals: list, color: str) -> str:
    """Mini línea de los últimos días."""
    if len(vals) < 2:
        return ""
    W, H, mx = 96, 30, max(1, *vals)
    X = lambda i: i / (len(vals) - 1) * W
    Y = lambda v: H - 3 - (v / mx) * (H - 6)
    d = "".join(f"{'L' if i else 'M'}{X(i):.1f},{Y(v):.1f}" for i, v in enumerate(vals))
    return (f'<svg class="spark" viewBox="0 0 {W} {H}"><path d="{d} L{W},{H} L0,{H}Z" fill="{color}" opacity=".12"/>'
            f'<path d="{d}" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>')


def gauge(v, color: str) -> str:
    """Medidor semicircular de probabilidad."""
    dash = 0 if nulo(v) else max(0.5, float(v) * 100)
    return ('<svg width="150" height="86" viewBox="0 0 150 86"><path d="M15 78 A60 60 0 0 1 135 78" fill="none" '
            'stroke="var(--card-3)" stroke-width="12" stroke-linecap="round"/>'
            f'<path d="M15 78 A60 60 0 0 1 135 78" fill="none" stroke="{color}" stroke-width="12" stroke-linecap="round" '
            f'pathLength="100" stroke-dasharray="{dash} 100"/></svg>')


def grafica_clima(lc: pd.DataFrame, sensor: pd.DataFrame, campo: str, h: float, horas: int, ini: str | None, *,
                  vmin: float, vmax: float, unidad: str, color: str, umbral: float | None = None) -> str:
    """HR o T de las últimas horas: línea del sensor del bloque y puntos del robot en la cama."""
    W, H, pl, pr, pt, pb = 520, 150, 34, 10, 10, 22
    x0 = h - horas
    X = lambda x: pl + (x - x0) / ((h - x0) or 1) * (W - pl - pr)
    Y = lambda y: pt + (1 - (min(max(y, vmin), vmax) - vmin) / (vmax - vmin)) * (H - pt - pb)
    g = (f'<defs><linearGradient id="g_{campo}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" style="stop-color:{color}" '
         f'stop-opacity=".28"/><stop offset="1" style="stop-color:{color}" stop-opacity="0"/></linearGradient></defs>')
    for i in range(4):
        val = vmin + (vmax - vmin) * i / 3
        y = Y(val)
        g += (f'<line x1="{pl}" x2="{W - pr}" y1="{y}" y2="{y}" style="stroke:var(--border)"/>'
              f'<text x="{pl - 6}" y="{y + 4}" style="fill:var(--faint)" font-size="10" text-anchor="end">{round(val)}</text>')
    d = math.ceil(x0 / 24) * 24
    while d <= h:
        x = X(d)
        anc = "end" if x > W - 40 else "start" if x < pl + 20 else "middle"
        g += f'<text x="{x}" y="{H - 5}" style="fill:var(--faint)" font-size="10" text-anchor="{anc}">{T.corta(d, ini)}</text>'
        d += 24
    if umbral is not None:
        y = Y(umbral)
        g += f'<line x1="{pl}" x2="{W - pr}" y1="{y}" y2="{y}" style="stroke:var(--alto)" stroke-dasharray="4 4" opacity=".8"/>'
    s = sensor[sensor["hora"] >= x0] if len(sensor) else sensor
    if len(s) > 1:
        pts = list(zip(s["hora"], s[campo]))
        line = "".join(f"{'L' if i else 'M'}{X(a):.1f},{Y(b):.1f}" for i, (a, b) in enumerate(pts))
        g += (f'<path d="{line} L{X(pts[-1][0]):.1f},{H - pb} L{X(pts[0][0]):.1f},{H - pb}Z" fill="url(#g_{campo})"/>'
              f'<path d="{line}" fill="none" style="stroke:var(--muted)" stroke-width="1.6" stroke-linejoin="round"/>')
    for r in lc.itertuples():
        val = getattr(r, campo)
        g += (f'<circle cx="{X(r.hora):.1f}" cy="{Y(val):.1f}" r="4" style="fill:var(--accent);stroke:var(--card)" '
              f'stroke-width="2"><title>{T.etiqueta(r.hora, ini)} · {val:g} {unidad}</title></circle>')
    if not len(s) and not len(lc):
        g += f'<text x="{W / 2}" y="{H / 2}" style="fill:var(--muted)" text-anchor="middle" font-size="12">Sin lecturas todavía</text>'
    return f'<svg class="chart" viewBox="0 0 {W} {H}">{g}</svg>'


def grafica_riesgo(serie: pd.DataFrame, alto: float, medio: float, ini: str | None) -> str:
    """Barras de probabilidad por día con las líneas de los umbrales."""
    if not len(serie):
        return '<div class="small muted">Aún no hay cálculos de riesgo.</div>'
    W, H, pl, pt, pb = 520, 120, 34, 10, 22
    n = len(serie)
    bw = (W - pl - 10) / n
    Y = lambda v: pt + (1 - v) * (H - pt - pb)
    g = ""
    for v, c in ((alto, "var(--alto)"), (medio, "var(--medio)")):
        g += (f'<line x1="{pl}" x2="{W - 10}" y1="{Y(v)}" y2="{Y(v)}" style="stroke:{c}" stroke-dasharray="4 4" opacity=".6"/>'
              f'<text x="{pl - 6}" y="{Y(v) + 4}" style="fill:var(--faint)" font-size="10" text-anchor="end">{round(v * 100)}%</text>')
    for i, r in enumerate(serie.itertuples()):
        w = min(26, bw * 0.62)
        x = pl + i * bw + (bw - w) / 2
        y = Y(r.prob_ia_7d)
        g += (f'<rect x="{x}" y="{y}" width="{w}" height="{max(2, H - pb - y)}" rx="5" fill="{rgb(rampa(RAMPA_RIESGO, r.prob_ia_7d))}">'
              f'<title>{T.corta(r.dia * 24, ini)} · {pct(r.prob_ia_7d)} · reglas {f2(r.riesgo_reglas)}</title></rect>')
        if n <= 8 or i % 2 == n % 2:
            g += f'<text x="{x + w / 2}" y="{H - 5}" style="fill:var(--faint)" font-size="10" text-anchor="middle">{T.corta(r.dia * 24, ini)}</text>'
    return f'<svg class="chart" viewBox="0 0 {W} {H}">{g}</svg>'


def area_riesgo(serie: pd.DataFrame, ini: str | None, vacio: str) -> str:
    """Área apilada de camas en riesgo alto y medio por día."""
    if len(serie) < 2:
        return vacio
    W, H, pl, pr, pt, pb = 900, 240, 36, 12, 12, 26
    filas = list(serie.itertuples())
    n = len(filas)
    mx = max(4, *(int(s.alto + s.medio) for s in filas))
    X = lambda i: pl + i / (n - 1) * (W - pl - pr)
    Y = lambda v: pt + (1 - v / mx) * (H - pt - pb)
    linea = lambda f: "".join(f"{'L' if i else 'M'}{X(i):.1f},{Y(f(s)):.1f}" for i, s in enumerate(filas))
    area = lambda ft, fb: linea(ft) + " " + "".join(f"L{X(i):.1f},{Y(fb(s)):.1f}" for i, s in reversed(list(enumerate(filas)))) + "Z"
    g = ""
    for k in range(5):
        v = mx * k / 4
        y = Y(v)
        g += (f'<line x1="{pl}" x2="{W - pr}" y1="{y}" y2="{y}" style="stroke:var(--border)"/>'
              f'<text x="{pl - 8}" y="{y + 4}" style="fill:var(--faint)" font-size="11" text-anchor="end">{round(v)}</text>')
    cada = max(1, math.ceil(n / 8))
    for i, s in enumerate(filas):
        if i % cada == 0 or i == n - 1:
            anc = "start" if i == 0 else "end" if i == n - 1 else "middle"
            g += f'<text x="{X(i)}" y="{H - 6}" style="fill:var(--faint)" font-size="11" text-anchor="{anc}">{T.corta(s.dia * 24, ini)}</text>'
    g += (f'<path d="{area(lambda s: s.alto + s.medio, lambda s: s.alto)}" style="fill:var(--medio)" opacity=".28"/>'
          f'<path d="{area(lambda s: s.alto, lambda s: 0)}" style="fill:var(--alto)" opacity=".32"/>')
    g += (f'<path d="{linea(lambda s: s.alto + s.medio)}" fill="none" style="stroke:var(--medio)" stroke-width="2"/>'
          f'<path d="{linea(lambda s: s.alto)}" fill="none" style="stroke:var(--alto)" stroke-width="2.2"/>')
    g += "".join(f'<rect x="{X(i) - 6}" y="{pt}" width="12" height="{H - pt - pb}" fill="transparent">'
                 f'<title>{T.corta(s.dia * 24, ini)} · alto {int(s.alto)} · medio {int(s.medio)}</title></rect>'
                 for i, s in enumerate(filas))
    return f'<svg class="chart" viewBox="0 0 {W} {H}">{g}</svg>'


def dona(partes: list[tuple], total: int) -> str:
    """Dona con el total al centro."""
    r, acc = 48, 0.0
    g = f'<circle r="{r}" fill="none" style="stroke:var(--card-3)" stroke-width="16"/>'
    if total:
        for v, c in partes:
            if not v:
                continue
            frac = v / total * 100
            g += (f'<circle r="{r}" fill="none" style="stroke:{c}" stroke-width="16" pathLength="100" '
                  f'stroke-dasharray="{frac} {100 - frac}" stroke-dashoffset="{-acc}" transform="rotate(-90)"/>')
            acc += frac
    return (f'<svg width="130" height="130" viewBox="-65 -65 130 130">{g}<text y="6" text-anchor="middle" font-size="22" '
            f'font-weight="750" style="fill:var(--text)">{total}</text></svg>')


def timeline_inc(i: dict, segs: pd.DataFrame, horas_tratamiento: float, ini: str | None) -> str:
    """Línea de tiempo de una incidencia: sospecha, confirmación, tratamiento, revisitas y cierre."""
    ev = [(i["hora_creada"], "var(--info)", "Sospecha detectada por el robot",
           "Visita prioritaria por predicción de riesgo" if i["origen"] == "prediccion" else "Patrulla rutinaria")]
    if not nulo(i["hora_confirmada"]):
        pref = "" if len(segs) else plural(0 if nulo(i["plantas_afectadas"]) else i["plantas_afectadas"], "planta afectada", "plantas afectadas") + " · "
        ev.append((i["hora_confirmada"], "var(--crit)", "Confirmada", f"{pref}confianza {f2(i['confianza'])}"))
    if i["estado"] == "descartada":
        ev.append((i["hora_cerrada"], "var(--faint)", "Descartada",
                   f"La inspección de cerca no confirmó (confianza {f2(i['confianza'])})"))
    if i["estado"] in ("en_tratamiento", "en_seguimiento", "cerrada") or len(segs):
        h = None if nulo(i["hora_confirmada"]) else i["hora_confirmada"] + horas_tratamiento
        ev.append((h, "var(--adv)", "Tratamiento aplicado", "Personal de campo"))
    for s in segs.itertuples():
        ev.append((s.hora, V_RES[s.resultado], f"{LABEL['res'][s.resultado]} · {plural(s.plantas_afectadas, 'planta', 'plantas')}",
                   f"{esc(s.nota)} · robot {esc(s.robot_id)}"))
    if i["estado"] == "cerrada":
        ev.append((i["hora_cerrada"], "var(--ok)", "Cerrada", "Dos revisitas limpias seguidas"))
    filas = "".join(f'<div class="ev" style="--c:{c}"><div class="h">{"" if nulo(h) else T.etiqueta(h, ini)}</div>'
                    f'<div class="t">{t}</div><div class="small muted">{s}</div></div>' for h, c, t, s in ev)
    return f'<div class="tl">{filas}</div>'

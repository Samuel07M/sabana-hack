"""Pantalla Análisis: tarjetas, camas en riesgo por día, origen de las detecciones y alertas por tipo."""
from dashboard.componentes.estado import Ctx
from dashboard.componentes.graficas import area_riesgo, dona
from dashboard.componentes.ui import LABEL, f1, html, ico_box, nulo, pct, plural
from hub import db


def pantalla(ctx: Ctx) -> None:
    """Desempeño del sistema en la temporada."""
    m = db.metricas(ctx.corrida).iloc[0].to_dict()
    serie = db.serie_riesgo(ctx.corrida)
    n_resp = int(m["n_resp"])
    tiles = [
        ("clock", "var(--accent)", "—" if nulo(m["respuesta"]) else f"{f1(m['respuesta'])} h", "Respuesta tras la alerta",
         f"Entre la alerta a 7 días y la confirmación ({plural(n_resp, 'caso', 'casos')})" if n_resp
         else "Aún sin casos confirmados tras una alerta"),
        ("check", "var(--ok)", pct(m["tasa"]), "Tasa de confirmación", f"{int(m['conf'])} confirmadas · {int(m['desc'])} descartadas"),
        ("drone", "var(--insp)", pct(m["cobertura"]), "Cobertura del dron · 24 h", "Camas medidas directamente"),
        ("repeat", "var(--info)", int(m["revisitas"]), "Revisitas automáticas", "Registradas por el dron"),
    ]
    pred, patr = int(m["origen_prediccion"]), int(m["origen_patrulla"])
    por_tipo = {t: int(m[f"tipo_{t}"]) for t in LABEL["tipo"]}
    max_t = max(1, *por_tipo.values())
    vacio = (f'<div class="empty" style="padding:30px">{ico_box("chart", "var(--accent)")}'
             '<div>Se mostrará cuando haya al menos dos días de cálculo.</div></div>')
    html(
        '<div class="stack"><div class="grid4">'
        + "".join(f'<div class="card tile">{ico_box(i, c, True, 16)}<div class="v">{v}</div><div class="l">{l}</div>'
                  f'<div class="d">{d}</div></div>' for i, c, v, l, d in tiles)
        + '</div><div class="card"><div class="card-hd"><div><h3>Camas en riesgo por día</h3><div class="sub">Cálculo diario '
          'del modelo a 7 días</div></div><div class="spacer"></div><div class="leyenda" style="margin:0"><span><i style="'
          'background:var(--alto)"></i>Alto</span><span><i style="background:var(--medio)"></i>Medio</span></div></div>'
        + area_riesgo(serie, ctx.ini, vacio)
        + '</div><div class="grid2"><div class="card"><div class="card-hd"><div><h3>Origen de las detecciones</h3>'
          '<div class="sub">Cómo encontró el dron cada caso</div></div></div><div class="row" style="gap:28px">'
        + dona([(pred, "var(--accent)"), (patr, "var(--insp)")], pred + patr)
        + f'<div class="stack" style="gap:12px"><div><div class="row" style="gap:8px"><span class="chip c-primary">'
          f'<span class="d"></span>Predicción</span><b class="num">{pred}</b></div><div class="tiny muted" style="margin-top:4px">'
          f'Visita prioritaria por riesgo alto</div></div><div><div class="row" style="gap:8px"><span class="chip c-insp">'
          f'<span class="d"></span>Patrulla</span><b class="num">{patr}</b></div><div class="tiny muted" style="margin-top:4px">'
          'Recorrido rutinario de camas</div></div></div></div></div>'
        + f'<div class="card"><div class="card-hd"><div><h3>Alertas por tipo</h3><div class="sub">'
          f'{plural(sum(por_tipo.values()), "alerta", "alertas")} en la temporada</div></div></div>'
        + "".join(f'<div class="hbar"><span>{LABEL["tipo"][t]}</span><div class="bar" style="--c:var(--accent)">'
                  f'<i style="width:{n / max_t * 100}%"></i></div><b class="num" style="text-align:right">{n}</b></div>'
                  for t, n in por_tipo.items())
        + f'<div class="small muted" style="margin-top:10px">Plantas afectadas en incidencias abiertas: '
          f'<b style="color:var(--text)">{int(m["plantas"])}</b></div></div></div></div>')

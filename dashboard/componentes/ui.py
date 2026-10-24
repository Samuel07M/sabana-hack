"""Piezas de interfaz del prototipo: íconos, etiquetas, colores, rampas y HTML pequeño."""
import html as _html
import math
from urllib.parse import quote

import streamlit as st

# ── íconos (mismos trazos del prototipo) ─────────────────────────────────────
I = {
    "map": '<path d="M3 6.5 9 3.5l6 3 6-3v14l-6 3-6-3-6 3z"/><path d="M9 3.5v14M15 6.5v14"/>',
    "bell": '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>',
    "clip": '<rect x="8" y="2" width="8" height="4" rx="1"/><path d="M16 4h2a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h2"/><path d="m9 14 2 2 4-4"/>',
    "wind": '<path d="M17.7 7.7a2.5 2.5 0 1 1 1.8 4.3H2"/><path d="M9.6 4.6A2 2 0 1 1 11 8H2"/><path d="M12.6 19.4A2 2 0 1 0 14 16H2"/>',
    "chart": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
    "robot": '<circle cx="12" cy="12" r="2.2"/><circle cx="5" cy="5" r="2.6"/><circle cx="19" cy="5" r="2.6"/><circle cx="5" cy="19" r="2.6"/><circle cx="19" cy="19" r="2.6"/><path d="m7 7 3.3 3.3M17 7l-3.3 3.3M7 17l3.3-3.3M17 17l-3.3-3.3"/>',
    "drop": '<path d="M12 22a7 7 0 0 0 7-7c0-2-1-3.9-3-5.5s-3.5-4-4-6.5c-.5 2.5-2 4.9-4 6.5C6 11.1 5 13 5 15a7 7 0 0 0 7 7z"/>',
    "thermo": '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3"/><path d="M12 9v4"/><path d="M12 17h.01"/>',
    "trend": '<path d="m22 7-8.5 8.5-5-5L2 17"/><path d="M16 7h6v6"/>',
    "activity": '<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>',
    "repeat": '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>',
    "check": '<circle cx="12" cy="12" r="10"/><path d="m9 12 2 2 4-4"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
    "xcircle": '<circle cx="12" cy="12" r="10"/><path d="m15 9-6 6M9 9l6 6"/>',
    "octagon": '<path d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86z"/><path d="M12 8v4M12 16h.01"/>',
    "chev": '<path d="m6 9 6 6 6-6"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>',
    "moon": '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>',
    "download": '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="m7 10 5 5 5-5"/><path d="M12 15V3"/>',
    "battery": '<rect x="2" y="7" width="16" height="10" rx="2"/><path d="M22 11v2"/>',
    "clock": '<circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>',
    "radio": '<path d="M4.9 19.1C1 15.2 1 8.8 4.9 4.9"/><path d="M7.8 16.2c-2.3-2.3-2.3-6.1 0-8.5"/><circle cx="12" cy="12" r="2"/><path d="M16.2 7.8c2.3 2.3 2.3 6.1 0 8.5"/><path d="M19.1 4.9C23 8.8 23 15.1 19.1 19"/>',
    "phone": '<rect x="5" y="2" width="14" height="20" rx="2.5"/><path d="M12 18h.01"/>',
    "leaf": '<path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/>',
    "edge": '<rect x="3" y="3" width="18" height="18" rx="2" stroke-dasharray="3 3"/>',
}

# ── etiquetas y colores (LABEL, C_*, V_* del prototipo) ──────────────────────
LABEL = {
    "nivel": {"bajo": "Bajo", "medio": "Medio", "alto": "Alto", "sindato": "Sin dato"},
    "sev": {"info": "Info", "advertencia": "Advertencia", "critica": "Crítica"},
    "tipo": {"riesgo_7d": "Riesgo a 7 días", "confirmacion": "Confirmación", "seguimiento": "Seguimiento",
             "ventilacion": "Ventilación", "descartada": "Descartada"},
    "inc": {"sospecha": "Sospecha", "confirmada": "Confirmada", "en_tratamiento": "En tratamiento",
            "en_seguimiento": "En seguimiento", "cerrada": "Cerrada", "descartada": "Descartada"},
    "robot": {"patrulla": "Patrulla", "prioridad": "Prioridad", "inspeccionando": "Inspeccionando", "carga": "Cargando"},
    "res": {"empeora": "Empeora", "igual": "Igual", "mejora": "Mejora", "limpia": "Limpia"},
    "origen": {"prediccion": "Predicción", "patrulla": "Patrulla"},
    "accion": {"inspeccion_priorizada": "Priorizar inspección", "monitorear": "Monitorear", "ignorar": "Ignorar",
               "tratamiento_programado": "Tratamiento programado", "tratamiento_aplicado": "Tratamiento aplicado",
               "continuar_seguimiento": "Continuar seguimiento", "retratar": "Volver a tratar",
               "entendido": "Entendido"},
}
TIPO_IC = {"riesgo_7d": "trend", "confirmacion": "octagon", "seguimiento": "repeat", "ventilacion": "wind",
           "descartada": "xcircle"}
SEV_V = {"critica": "var(--crit)", "advertencia": "var(--adv)", "info": "var(--info)"}
C_INC = {"sospecha": "c-info", "confirmada": "c-critica", "en_tratamiento": "c-advertencia",
         "en_seguimiento": "c-primary", "cerrada": "c-ok", "descartada": "c-mute"}
V_INC = {"sospecha": "var(--info)", "confirmada": "var(--crit)", "en_tratamiento": "var(--adv)",
         "en_seguimiento": "var(--accent)", "cerrada": "var(--ok)", "descartada": "var(--faint)"}
C_ROBOT = {"patrulla": "c-primary", "prioridad": "c-advertencia", "inspeccionando": "c-insp", "carga": "c-mute"}
V_ROBOT = {"patrulla": "var(--accent)", "prioridad": "var(--adv)", "inspeccionando": "var(--insp)",
          "carga": "var(--faint)"}
V_RES = {"empeora": "var(--crit)", "igual": "var(--adv)", "mejora": "var(--accent)", "limpia": "var(--ok)"}
ABIERTA = lambda e: e not in ("cerrada", "descartada")

RAMPA_RIESGO = [(0, (78, 128, 128)), (0.3, (118, 182, 142)), (0.45, (228, 190, 96)), (0.6, (240, 136, 88)),
                (1, (232, 74, 94))]
RAMPA_HR = [(0, (206, 190, 148)), (0.45, (120, 176, 206)), (1, (82, 98, 226))]


# ── formato ──────────────────────────────────────────────────────────────────
def nulo(x) -> bool:
    """True si x es None o NaN."""
    return x is None or (isinstance(x, float) and math.isnan(x))


def esc(s) -> str:
    """Escapa texto para HTML."""
    return _html.escape("" if nulo(s) else str(s), quote=True)


def f2(x) -> str:
    """Dos decimales o '—'."""
    return "—" if nulo(x) else f"{float(x):.2f}"


def f1(x) -> str:
    """Un decimal o '—'."""
    return "—" if nulo(x) else f"{float(x):.1f}"


def pct(x) -> str:
    """'74 %' o '—' (redondeo como Math.round)."""
    return "—" if nulo(x) else f"{math.floor(float(x) * 100 + 0.5)} %"


def plural(n, s: str, p: str) -> str:
    """'1 cama' / '3 camas'."""
    n = int(n)
    return f"{n} {s if n == 1 else p}"


def entero(x):
    """int o None."""
    return None if nulo(x) else int(x)


# ── color ────────────────────────────────────────────────────────────────────
def rampa(stops, v: float) -> tuple:
    """Color interpolado de una rampa en v ∈ [0, 1]."""
    v = max(0.0, min(1.0, float(v)))
    for (a, ca), (b, cb) in zip(stops, stops[1:]):
        if v <= b:
            k = (v - a) / ((b - a) or 1)
            return tuple(x + (y - x) * k for x, y in zip(ca, cb))
    return stops[-1][1]


def rgb(c, f: float = 1) -> str:
    """'rgb(r,g,b)' con factor de brillo."""
    return "rgb(" + ",".join(str(int(round(max(0, min(255, x * f))))) for x in c) + ")"


def color_riesgo(p) -> str:
    """Color de la rampa de riesgo para una probabilidad."""
    return rgb(rampa(RAMPA_RIESGO, p))


def grad_css(stops) -> str:
    """linear-gradient de una rampa."""
    return "linear-gradient(90deg," + ",".join(f"{rgb(c)} {round(v * 100)}%" for v, c in stops) + ")"


# ── HTML pequeño ─────────────────────────────────────────────────────────────
def ic(nombre: str, s: int = 18, w: float = 1.8) -> str:
    """Ícono SVG en línea."""
    return (f'<svg class="ic" width="{s}" height="{s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            f'stroke-width="{w}" stroke-linecap="round" stroke-linejoin="round">{I.get(nombre, "")}</svg>')


def chip(txt: str, cls: str, dot: bool = True, extra: str = "", estilo: str = "") -> str:
    """Chip de color con punto opcional."""
    st_ = f' style="{estilo}"' if estilo else ""
    return f'<span class="chip {cls} {extra}"{st_}>{"<span class=d></span>" if dot else ""}{esc(txt)}</span>'


def ico_box(nombre: str, color: str, sm: bool = False, s: int = 18) -> str:
    """Cuadro de color con ícono."""
    return f'<div class="ico-box {"sm" if sm else ""}" style="--c:{color}">{ic(nombre, s)}</div>'


def nivel_var(n: str) -> str:
    """Variable CSS del color de un nivel."""
    return {"bajo": "var(--bajo)", "medio": "var(--medio)", "alto": "var(--alto)"}.get(n, "var(--faint)")


def mascara(nombre: str, color: str = "black") -> str:
    """URL data: del ícono para usarlo como máscara CSS (íconos en botones de Streamlit)."""
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{color}" '
           f'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{I[nombre]}</svg>')
    return f'url("data:image/svg+xml,{quote(svg)}")'


def css_icono(clave: str, nombre: str, s: int = 16) -> str:
    """Regla CSS que pone un ícono antes del texto del botón con key=clave."""
    m = mascara(nombre)
    return (f'.st-key-{clave} button::before{{content:"";width:{s}px;height:{s}px;flex:none;background:currentColor;'
            f'-webkit-mask:{m} center/contain no-repeat;mask:{m} center/contain no-repeat}}')


# ── Streamlit ────────────────────────────────────────────────────────────────
def html(s: str, dest=None, width="stretch") -> None:
    """Pinta HTML (en una sola línea para que Markdown no lo convierta en código)."""
    (dest or st).markdown(" ".join(line.strip() for line in s.splitlines()), unsafe_allow_html=True, width=width)


def estilo(css: str, dest=None) -> None:
    """Inyecta CSS."""
    (dest or st).markdown(f"<style>{css}</style>", unsafe_allow_html=True)


def clicable(clave: str, contenido: str, on_click=None, args=(), ayuda: str | None = None, dest=None) -> bool:
    """HTML del prototipo con un botón invisible encima: devuelve True al hacer clic."""
    with (dest or st).container(key=f"clk_{clave}"):
        html(contenido)
        return st.button("·", key=f"btn_{clave}", on_click=on_click, args=args, help=ayuda)

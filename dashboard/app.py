"""Dashboard de Atalaya (Streamlit): migración de dashboard/prototipo.html.

    $env:FINCA_DB = "data\\mock.db"; streamlit run dashboard/app.py
    Corrida por URL: ?corrida=demo | temporada-7 | celular-12
    Tour guiado (dashboard/tour): ?tour=1 lo fuerza, ?tour=0 lo apaga, ?paso=6 arranca en ese paso
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from dashboard.componentes import alertas, analisis, detalle, estilos, incidencias, panorama, ventilacion  # noqa: E402
from dashboard import tour  # noqa: E402
from dashboard.componentes.estado import aplicar_tope, contexto, iniciar, mostrar_aviso  # noqa: E402
from dashboard.componentes.navegacion import barra_superior, lateral  # noqa: E402
from dashboard.componentes.ui import html  # noqa: E402
from hub import db  # noqa: E402
from hub.config import cargar  # noqa: E402

ICONO = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='12' cy='18' "
         "r='9' fill='%235B6CF0'/%3E%3Ccircle cx='21' cy='13' r='8' fill='%238B5CF6'/%3E%3C/svg%3E")
PANTALLAS = {"finca": panorama.pantalla, "alertas": alertas.pantalla, "incidencias": incidencias.pantalla,
             "ventilacion": ventilacion.pantalla, "analisis": analisis.pantalla}
CFG = cargar()
REFRESCO = CFG["dashboard"]["refresco_s"]


def corrida_elegida() -> str | None:
    """La del tour si está corriendo; si no, la de ?corrida= (por defecto la del YAML); None si no existe en la base."""
    pedida = st.session_state.corrida_tour or st.query_params.get("corrida", CFG["dashboard"]["corrida_por_defecto"])
    ids = list(db.corridas()["corrida_id"])
    return pedida if pedida in ids else None


def avisos_criticos(corrida: str) -> None:
    """st.toast cuando entra una alerta crítica nueva (no al abrir la página)."""
    ss = st.session_state
    crit = db.alertas(corrida, severidad="critica", orden="recientes")
    nuevas = crit[~crit["alerta_id"].isin(ss.criticas_vistas)]
    ss.criticas_vistas.update(int(x) for x in nuevas["alerta_id"])
    if not ss.primera and len(nuevas):
        a = nuevas.iloc[0]
        mas = f" (+{len(nuevas) - 1} más)" if len(nuevas) > 1 else ""
        st.toast(f"**{a['titulo']}**  \n{a['mensaje']}{mas}", icon=":material/report:", duration="long")
    ss.primera = False


@st.fragment(run_every=REFRESCO)
def menu(corrida: str) -> None:
    """Menú lateral con contadores y estado de red."""
    aplicar_tope(corrida)
    lateral(corrida)


@st.fragment(run_every=REFRESCO)
def principal(corrida: str) -> None:
    """Recuadro del tour, barra superior y pantalla actual."""
    tour.componente()
    ctx = contexto(corrida)
    avisos_criticos(corrida)
    barra_superior(ctx)
    PANTALLAS[st.session_state.tab](ctx)


def main() -> None:
    """Arma la página."""
    st.set_page_config(page_title="Atalaya · Sistema de Monitoreo", page_icon=ICONO, layout="wide",
                       initial_sidebar_state="expanded")
    iniciar()
    estilos.inyectar(st.session_state.tema)
    if not db.existe():
        html(f'<div class="card empty" style="margin-top:40px">No se encontró la base <b>{db.ruta_base()}</b>.<br>'
             'Genera los datos de prueba con <code>python -m hub.mock</code> y usa '
             '<code>$env:FINCA_DB = "data\\mock.db"</code>.</div>')
        return
    tour.desde_url()
    corrida = corrida_elegida()
    if corrida is None:
        ids = ", ".join(db.corridas()["corrida_id"])
        html(f'<div class="card empty" style="margin-top:40px">La corrida pedida no está en la base. Disponibles: {ids}.</div>')
        return
    mostrar_aviso()
    with st.sidebar:
        menu(corrida)
    principal(corrida)
    if st.session_state.cama:
        detalle.abrir(corrida)


main()

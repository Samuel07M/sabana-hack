"""Estado de la sesión (lo que en el prototipo vivía en el objeto UI) y contexto de cada refresco."""
from dataclasses import dataclass

import streamlit as st

from hub import db
from hub.config import cargar

INICIAL = {
    "tab": "finca", "bloque": 1, "cama": None, "abiertas": set(), "f_estado": "todas", "f_bloque": "todos",
    "traza": "todos", "inc_filtro": "abiertas", "inc_sel": None, "criticas_vistas": set(), "primera": True,
    "tema": "dark", "ult_click": None, "aviso": None,
    "tour": None, "repro": None, "corrida_tour": None, "tour_auto": False, "mapa_capa": None,   # dashboard/tour
}


@dataclass
class Ctx:
    """Lo que necesita cada pantalla en un refresco."""
    corrida: str
    ahora: float
    ini: str | None
    red: str
    cfg: dict

    @property
    def sin_red(self) -> bool:
        """True en modo sin red (escenario robots_celular)."""
        return self.red == "sin_red"


def iniciar() -> None:
    """Valores por defecto de la sesión."""
    for k, v in INICIAL.items():
        if k not in st.session_state:
            st.session_state[k] = v.copy() if isinstance(v, set) else v


def aplicar_tope(corrida: str) -> None:
    """Tope de reproducción de la sesión (tour guiado) para las consultas de esta corrida; None = en vivo."""
    r = st.session_state.get("repro")
    db.fijar_tope(r["tope"] if r and r["corrida"] == corrida else None)


def contexto(corrida: str) -> Ctx:
    """Contexto con la hora y la red actuales (con el tope de reproducción aplicado)."""
    aplicar_tope(corrida)
    return Ctx(corrida, db.ahora(corrida), db.inicio_sim(corrida), db.red(corrida), cargar())


def ir_a(tab: str) -> None:
    """Cambia de pantalla."""
    st.session_state.tab = tab


def abrir_cama(cama_id: str) -> None:
    """Abre el detalle de una cama y pone su bloque en el mapa."""
    st.session_state.cama = cama_id
    st.session_state.bloque = int(cama_id[1:cama_id.index("-")])


def cerrar_cama() -> None:
    """Cierra el detalle de cama."""
    st.session_state.cama = None


def avisar(titulo: str, mensaje: str, icono: str = ":material/check_circle:") -> None:
    """Deja un aviso para mostrarlo con st.toast después del siguiente rerun."""
    st.session_state.aviso = (titulo, mensaje, icono)


def mostrar_aviso() -> None:
    """Muestra el aviso pendiente, si hay."""
    a = st.session_state.get("aviso")
    if a:
        st.session_state.aviso = None
        st.toast(f"**{a[0]}**  \n{a[1]}", icon=a[2])

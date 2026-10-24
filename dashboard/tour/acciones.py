"""Acciones de los pasos del tour: llevan el dashboard a la vista del paso (solo estado de sesión, nunca escriben la base).

Cada acción recibe la corrida y puede devolver otra corrida para mostrar (el paso "Sin internet").
"""
import streamlit as st

from dashboard.componentes.estado import abrir_cama
from hub import db


def pantalla(tab: str, bloque: int = 1, capa: str | None = None):
    """Abre una pantalla sin detalle de cama; en Panorama, el bloque y la capa del mapa (riesgo | humedad)."""
    def accion(corrida: str) -> None:
        ss = st.session_state
        ss.tab, ss.cama, ss.bloque, ss.mapa_capa = tab, None, bloque, capa
    return accion


def cama(cama_id: str):
    """Panorama con el detalle de la cama abierto (panel de riesgo)."""
    def accion(corrida: str) -> None:
        ss = st.session_state
        ss.tab, ss.mapa_capa = "finca", "riesgo"
        abrir_cama(cama_id)
    return accion


def alerta(tipo: str, cama_id: str):
    """Pantalla Alertas sin filtros y con la alerta más reciente de ese tipo en la cama expandida."""
    def accion(corrida: str) -> None:
        ss = st.session_state
        ss.tab, ss.cama, ss.f_estado, ss.f_bloque = "alertas", None, "todas", "todos"
        al = db.alertas(corrida, tipo=tipo, orden="recientes")
        al = al[al["cama_id"] == cama_id]
        if len(al):
            ss.abiertas.add(int(al["alerta_id"].iloc[0]))
    return accion


def incidencia(cama_id: str):
    """Pantalla Incidencias con la incidencia más reciente de la cama seleccionada."""
    def accion(corrida: str) -> None:
        ss = st.session_state
        ss.tab, ss.cama, ss.inc_filtro = "incidencias", None, "todas"
        inc = db.incidencias(corrida, cama_id=cama_id)
        if len(inc):
            ss.inc_sel = int(inc["incidencia_id"].iloc[0])
    return accion


def ventilacion(bloque: int):
    """Pantalla Ventilación."""
    def accion(corrida: str) -> None:
        ss = st.session_state
        ss.tab, ss.cama, ss.bloque = "ventilacion", None, bloque
    return accion


def sin_red():
    """Cambia a una corrida sin red (escenario robots_celular) si existe; si no, se queda en la corrida del tour."""
    def accion(corrida: str) -> str | None:
        ss = st.session_state
        ss.cama = None
        cs = db.corridas()
        cel = cs[cs["escenario"] == "robots_celular"]["corrida_id"]
        return str(cel.iloc[0]) if len(cel) else None
    return accion

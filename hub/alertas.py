"""Ciclo de vida de las alertas: 'nueva' → 'vista' → 'resuelta' (solo hacia adelante) y acción del agrónomo."""
from contextlib import closing

import pandas as pd

from hub import db
from hub.config import cargar
from hub.db import conectar_escritura

ESTADOS = ("nueva", "vista", "resuelta")
TIPOS_PANTALLA = ("riesgo_7d", "confirmacion")              # pantalla Alertas
TIPOS_TRAZA = ("seguimiento", "ventilacion", "descartada")   # Trazabilidad, dentro de Incidencias


def puede_pasar(actual: str, nuevo: str) -> bool:
    """True si el cambio de estado va hacia adelante."""
    if actual not in ESTADOS or nuevo not in ESTADOS:
        return False
    return ESTADOS.index(nuevo) > ESTADOS.index(actual)


def acciones(tipo: str) -> list[str]:
    """Acciones permitidas para un tipo de alerta (dashboard.acciones del YAML)."""
    return list(cargar()["dashboard"]["acciones"].get(tipo, []))


def accion_valida(tipo: str, accion: str) -> bool:
    """True si la acción está permitida para el tipo."""
    return accion in acciones(tipo)


def _leer(con, alerta_id: int):
    """(tipo, estado) de una alerta o None."""
    return con.execute("SELECT tipo, estado FROM alertas WHERE alerta_id=?", (int(alerta_id),)).fetchone()


def marcar_vista(alerta_id: int) -> bool:
    """Pasa una alerta de 'nueva' a 'vista'; False si no correspondía."""
    with closing(conectar_escritura()) as con:
        cur = con.execute("UPDATE alertas SET estado='vista' WHERE alerta_id=? AND estado='nueva'", (int(alerta_id),))
        con.commit()
        return cur.rowcount > 0


def resolver(alerta_id: int, accion: str) -> bool:
    """Resuelve la alerta con una acción permitida para su tipo; False si no se puede."""
    with closing(conectar_escritura()) as con:
        fila = _leer(con, alerta_id)
        if not fila or not puede_pasar(fila[1], "resuelta") or not accion_valida(fila[0], accion):
            return False
        cur = con.execute("UPDATE alertas SET estado='resuelta', accion=? WHERE alerta_id=? AND estado!='resuelta'",
                          (accion, int(alerta_id)))
        con.commit()
        return cur.rowcount > 0


def de_pantalla(corrida_id: str, tipo: str | None = None, estado: str | None = None,
                bloque=None) -> pd.DataFrame:
    """Alertas de la pantalla Alertas (solo riesgo_7d y confirmacion), de la más reciente a la más antigua."""
    tipos = [tipo] if tipo in TIPOS_PANTALLA else list(TIPOS_PANTALLA)
    return db.alertas(corrida_id, estado=estado, tipos=tipos, bloque=bloque, orden="recientes")


def de_trazabilidad(corrida_id: str, tipo: str = "todos") -> pd.DataFrame:
    """Alertas de Trazabilidad (seguimiento, ventilacion y descartada), de la más reciente a la más antigua."""
    tipos = [tipo] if tipo in TIPOS_TRAZA else list(TIPOS_TRAZA)
    return db.alertas(corrida_id, tipos=tipos, orden="recientes")

"""Simulación del celular (nivel 2): descarga por Bluetooth lo guardado en los robots."""
import math
from contextlib import closing

from hub.db import ahora, conectar_escritura


def sincronizar(corrida_id: str, hora: float | None = None) -> int:
    """Pasa el celular: llena hora_recibida de lo pendiente y devuelve cuántos datos llegaron."""
    h = int(math.floor(ahora(corrida_id) if hora is None else hora))
    with closing(conectar_escritura()) as con:
        cur = con.execute("UPDATE cola_sync SET hora_recibida=? WHERE corrida_id=? AND hora_recibida IS NULL",
                          (h, corrida_id))
        con.commit()
        return cur.rowcount

"""Etiqueta a 7 días: usa la verdad del simulador, solo para entrenar y evaluar."""
import numpy as np

from sim.enfermedad import LATENTE


def etiquetas(cambios: np.ndarray, cama_de_planta: np.ndarray, n_camas: int, n_horas: int,
              hora: int, horizonte_h: int) -> np.ndarray:
    """y[cama] = 1 si alguna planta pasa de sana a latente en (hora, hora + horizonte_h]."""
    inf = cambios[cambios[:, 2] == LATENTE]
    ventana = (inf[:, 0] > hora) & (inf[:, 0] <= hora + horizonte_h)
    y = np.zeros(n_camas, dtype=int)
    y[cama_de_planta[inf[ventana, 1]]] = 1
    return y

"""Dron de cable: patrulla, prioridad, inspección, revisitas y batería (uno por bloque)."""
import numpy as np

from sim import enfermedad


def inspeccionar(estado: np.ndarray, d: dict, rng: np.random.Generator) -> tuple[np.ndarray, int, int]:
    """Plantas marcadas por la cámara en una cama: (posiciones 1-based, aciertos reales, falsos positivos)."""
    u = rng.random(estado.size)
    latente, sintomas = estado == enfermedad.LATENTE, estado == enfermedad.SINTOMAS
    vivas_sanas = (estado == enfermedad.SANA) | (estado == enfermedad.TRATADA)
    marca = (latente & (u < d["sens_latente"])) | (sintomas & (u < d["sens_sintomas"])) \
        | (vivas_sanas & (u < d["tasa_falsa_deteccion_planta"]))
    reales = int(np.count_nonzero(marca & (latente | sintomas)))
    return np.nonzero(marca)[0] + 1, reales, int(np.count_nonzero(marca)) - reales


class Dron:
    """Un dron por bloque; el estado real que mantiene es su reloj, su ruta y su batería."""

    def __init__(self, sim, bloque: int):
        n = sim.cfg["geometria"]["naves_por_bloque"] * sim.cfg["geometria"]["camas_por_nave"]
        self.bloque, self.id = bloque, f"B{bloque}"
        self.camas = np.arange((bloque - 1) * n, bloque * n)
        orden = list(range(n)) + list(range(n - 2, 0, -1))       # 1 → n → 1
        self.ruta, self.k = self.camas[orden], 0
        self.t, self.bateria, self.cama_actual = 0.0, 1.0, int(self.camas[0])

    def trabajar(self, sim, hora: int) -> None:
        """Actúa durante [hora, hora+1): carga, revisitas vencidas, prioridad y patrulla."""
        d = sim.cfg["drones"]
        dt = d["min_por_cama"] / 60.0
        self.t = max(self.t, float(hora))
        while self.t < hora + 1:
            if self.bateria <= d["bateria_min"]:
                sim.fila_dron(self, self.t, self.cama_actual, "carga")
                self.t += d["horas_carga"]
                self.bateria = 1.0
                continue
            objetivo = self._elegir(sim)
            if objetivo is None:
                self.t = hora + 1.0
                break
            cama, motivo = objetivo
            sim.visita(self, cama, motivo, self.t, dt)
            self.cama_actual = cama
            self.t += dt
            self.bateria -= dt / d["bateria_horas"]

    def _elegir(self, sim):
        """(cama, motivo) siguiente o None: revisita > prioridad > patrulla."""
        inc = sim.revisita_vencida(self.bloque, self.t)
        if inc is not None:
            return sim.inc[inc]["cama"], "revisita"
        cama = sim.prioridad(self.camas, self.t)
        if cama is not None:
            return cama, "prioridad"
        if sim.flags["patrulla"]:
            cama = int(self.ruta[self.k])
            self.k = (self.k + 1) % len(self.ruta)
            return cama, "patrulla"
        return None

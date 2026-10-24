"""Botrytis por planta: infección (Nair y Allen + núcleo espacial + aire), latencia, pérdida y tratamiento."""
import numpy as np
from scipy import sparse

SANA, LATENTE, SINTOMAS, TRATADA, PERDIDA = 0, 1, 2, 3, 4


def f_ambiental(T, W, p: dict, T_sin_infeccion: float):
    """Nair y Allen (1993): 1 − exp(−(Q·W/Ktime)²), Q = exp(−((T−Topt)/Ktemp)²); 0 si T > T_sin_infeccion."""
    Q = np.exp(-((T - p["T_opt"]) / p["K_temp"]) ** 2)
    f = 1.0 - np.exp(-((Q * W) / p["Ktime_h"]) ** 2)
    return np.where(T > T_sin_infeccion, 0.0, f)


class Enfermedad:
    """Estado de cada planta y su dinámica horaria (vectorizada)."""

    def __init__(self, cfg: dict, geo, rng: np.random.Generator, n_horas: int):
        e = cfg["enfermedad"]
        self.e, self.geo, self.n_horas = e, geo, n_horas
        self.p_na = e["nair_allen"][e["organo"]]
        n = geo.n_plantas
        self.estado = np.zeros(n, dtype=np.int8)
        self.t_cambio = np.full(n, np.inf)
        self.U = rng.random((n_horas, n), dtype=np.float32)       # sorteos comunes entre escenarios
        self.dur_latencia = rng.uniform(*e["latencia_dias"], n) * 24
        self.dur_perdida = rng.uniform(*e["sintomas_a_perdida_dias"], n) * 24
        self.Vb = self._vecindad_con_beta(e, geo)                  # β_cama·K en la misma cama, β_vec·K entre camas
        self.pv = np.zeros(n)                                      # tasa por vecinos ya multiplicada por β (incremental)
        self.peso = np.zeros(n)                                    # peso infeccioso actual por planta
        self.peso_cama = np.zeros(geo.n_camas)                     # suma del peso por cama (para el aire)
        self.focos = self._focos(cfg, rng)
        self.cambios: list[tuple] = []                             # (hora, planta, estado_nuevo)
        self.afectadas = np.zeros(n_horas, dtype=np.int32)         # latentes + síntomas + perdidas por hora

    @staticmethod
    def _vecindad_con_beta(e: dict, geo) -> sparse.csc_matrix:
        """Núcleo K con β_cama dentro de la cama (meta logística del PDF) y β_vec entre camas (meta 5,5 % del PDF)."""
        V = geo.V.tocoo()
        misma = geo.cama_de_planta[V.row] == geo.cama_de_planta[V.col]
        datos = V.data * np.where(misma, e["beta_cama"], e["beta_vec"])
        return sparse.csc_matrix((datos, (V.row, V.col)), shape=V.shape)

    def _focos(self, cfg: dict, rng: np.random.Generator) -> list[tuple[int, int]]:
        """Lista ordenada de (hora, planta) con los focos iniciales."""
        e, geo = self.e, self.geo
        if e["focos_forzados"]:
            P = geo.plantas_por_cama
            return sorted((f["hora"], geo.idx_cama[f["cama_id"]] * P + f["posicion"] - 1) for f in e["focos_forzados"])
        n = int(rng.integers(e["focos_por_temporada"][0], e["focos_por_temporada"][1] + 1))
        w = 1.0 + (e["foco_preferencia_borde"] - 1.0) * geo.es_borde_planta
        plantas = rng.choice(geo.n_plantas, size=n, replace=False, p=w / w.sum())
        v0, v1 = e["foco_ventana_dias"]
        horas = np.minimum(rng.integers(v0 * 24, v1 * 24 + 1, n), self.n_horas - 1)
        return sorted(zip(horas.tolist(), plantas.tolist()))

    def _fijar(self, plantas: np.ndarray, nuevo: int, hora: int) -> None:
        """Cambia el estado de `plantas`, actualiza presiones y registra el evento de verdad."""
        if plantas.size == 0:
            return
        w = {LATENTE: self.e["peso_latente"], SINTOMAS: self.e["peso_sintomas"]}.get(nuevo, 0.0)
        for i in plantas:
            delta = w - self.peso[i]
            if delta:
                ini, fin = self.Vb.indptr[i], self.Vb.indptr[i + 1]
                self.pv[self.Vb.indices[ini:fin]] += delta * self.Vb.data[ini:fin]
                self.peso_cama[self.geo.cama_de_planta[i]] += delta
                self.peso[i] = w
        self.estado[plantas] = nuevo
        self.cambios.extend((hora, int(i), nuevo) for i in plantas)

    def paso(self, hora: int, f_cama: np.ndarray, vent_encendida_cama: np.ndarray) -> None:
        """Avanza una hora: focos, infecciones nuevas y transiciones por tiempo."""
        e, geo = self.e, self.geo
        while self.focos and self.focos[0][0] <= hora:
            _, planta = self.focos.pop(0)
            if self.estado[planta] == SANA:
                self.t_cambio[planta] = hora + self.dur_latencia[planta]
                self._fijar(np.array([planta]), LATENTE, hora)
        if f_cama.any():
            pa = geo.A_aire @ (self.peso_cama * vent_encendida_cama)
            lam = (self.pv + e["beta_aire"] * pa[geo.cama_de_planta] + e["beta_0"]) \
                * f_cama[geo.cama_de_planta]
            nuevas = np.nonzero((self.estado == SANA) & (self.U[hora] < 1.0 - np.exp(-lam)))[0]
            self.t_cambio[nuevas] = hora + self.dur_latencia[nuevas]
            self._fijar(nuevas, LATENTE, hora)
        for origen, destino in ((LATENTE, SINTOMAS), (SINTOMAS, PERDIDA), (TRATADA, SANA)):
            due = np.nonzero((self.estado == origen) & (self.t_cambio <= hora))[0]
            if due.size:
                self.t_cambio[due] = hora + self.dur_perdida[due] if destino == SINTOMAS else np.inf
                self._fijar(due, destino, hora)
        self.afectadas[hora] = np.count_nonzero(np.isin(self.estado, (LATENTE, SINTOMAS, PERDIDA)))

    def tratar(self, cama: int, hora: int, rng: np.random.Generator) -> int:
        """Trata las plantas infectadas de la cama; devuelve cuántas quedaron tratadas."""
        P = self.geo.plantas_por_cama
        base = cama * P
        inf = base + np.nonzero(np.isin(self.estado[base:base + P], (LATENTE, SINTOMAS)))[0]
        ok = inf[rng.random(inf.size) < self.e["eficacia_tratamiento"]]
        self.t_cambio[ok] = hora + self.e["dias_proteccion"] * 24
        self._fijar(ok, TRATADA, hora)
        return int(ok.size)

    def estado_cama(self, cama: int) -> np.ndarray:
        """Estados de las plantas de una cama (vista)."""
        P = self.geo.plantas_por_cama
        return self.estado[cama * P:(cama + 1) * P]

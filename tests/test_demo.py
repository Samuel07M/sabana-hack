"""La demo debe producir la secuencia completa, con o sin modelo de IA (reglas de respaldo)."""
import sqlite3

import pytest

from sim import run_vivo
from sim.config import RAIZ, cargar_config
from sim.motor import Simulacion

CAMA = "B1-N2-C14"


def _correr(modelo):
    cfg = cargar_config(RAIZ / "config" / "demo.yaml")
    sim = Simulacion(cfg, "demo", cfg["semilla"], "demo", modo="vivo", modelo=modelo)
    for h in range(sim.n_horas):
        sim.paso(h)
    return sim


@pytest.mark.parametrize("modelo", [None, "auto"])
def test_secuencia_de_la_demo(modelo):
    sim = _correr(modelo)
    alertas = [(a[2], a[6], a[3], a[5]) for a in sim.buf["alertas"]]
    riesgo = min(h for h, tipo, cama, _ in alertas if tipo == "riesgo_7d" and cama == CAMA)
    conf = min(h for h, tipo, cama, sev in alertas if tipo == "confirmacion" and cama == CAMA and sev == "critica")
    vent = min(v[1] for v in sim.buf["ventilacion"] if v[4] == "apagada")
    inc = next(i for i in sim.inc.values() if sim.geo.camas[i["cama"]]["cama_id"] == CAMA)
    seg = [s for s in sim.buf["seguimientos"] if s[1] == inc["id"]]
    assert riesgo < conf <= vent                       # alerta de riesgo → confirmación → ventilación apagada
    assert inc["origen"] == "prediccion"               # el dron fue por prioridad, no por patrulla
    assert seg and seg[0][5] == "mejora" and seg[0][3] - inc["hora_confirmada"] >= 72    # seguimiento ≥ 3 días después
    assert sim.buf["cola_sync"] and all(f[4] is None for f in sim.buf["cola_sync"])      # paso "Sin red"


def test_run_vivo_escribe_hora_a_hora_y_se_puede_leer_mientras_tanto(tmp_path):
    db = tmp_path / "finca.db"
    run_vivo.main(["--config", str(RAIZ / "config" / "demo.yaml"), "--velocidad", "0", "--db", str(db), "--horas", "60"])
    con = sqlite3.connect(db)
    assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert con.execute("SELECT modo, escenario FROM corridas").fetchone() == ("vivo", "demo")
    assert con.execute("SELECT COUNT(*) FROM camas").fetchone()[0] == 72
    assert con.execute("SELECT COUNT(*) FROM cola_sync WHERE hora_recibida IS NULL").fetchone()[0] > 0
    assert con.execute("SELECT MAX(hora) FROM lecturas").fetchone()[0] == 59
    con.close()

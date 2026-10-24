"""Textos de las alertas (una función por tipo) y su severidad desde la config."""
from sim.valores import SEVERIDADES, TIPOS_ALERTA


def ubicacion(cama: dict) -> str:
    """'B1 · Nave 2 · Cama 14'."""
    return f"B{cama['bloque']} · Nave {cama['nave']} · Cama {cama['cama']}"


def _plantas(n: int) -> str:
    """'1 planta afectada' / '3 plantas afectadas'."""
    return f"{n} planta afectada" if n == 1 else f"{n} plantas afectadas"


def severidad(cfg: dict, tipo: str, empeora: bool = False) -> str:
    """Severidad de la alerta según config.alertas.severidad."""
    clave = "seguimiento_empeora" if (tipo == "seguimiento" and empeora) else tipo
    sev = cfg["alertas"]["severidad"][clave]
    if tipo not in TIPOS_ALERTA or sev not in SEVERIDADES:
        raise ValueError(f"alerta fuera del contrato: tipo={tipo} severidad={sev}")
    return sev


def riesgo_7d(cama, prob, horas_mojado, nivel_broome, cfg) -> tuple[str, str]:
    """(titulo, mensaje) de una alerta riesgo_7d; explica si las reglas de Broome coinciden o si el aviso viene solo de la IA."""
    if nivel_broome in ("moderado", "alto"):
        motivo = f"Mojado continuo de {horas_mojado:.0f} h (índice de Broome: {nivel_broome})."
    else:
        motivo = (f"Mojado continuo de {horas_mojado:.0f} h: las reglas de Broome solas no lo marcarían ({nivel_broome}); "
                  "el aviso viene del modelo (humedad acumulada, bordes y camas vecinas).")
    return ("Riesgo alto de Botrytis",
            f"{ubicacion(cama)}: alto riesgo de Botrytis en los próximos 7 días (prob. {prob:.2f}). {motivo}")


def confirmacion(cama, posicion, afectadas, confianza) -> tuple[str, str]:
    """(titulo, mensaje) de una confirmación."""
    return ("Botrytis confirmada",
            f"Botrytis confirmada · {ubicacion(cama)} · posición {posicion}. "
            f"{_plantas(afectadas)} (confianza {confianza:.2f}).")


def descartada(cama, posicion) -> tuple[str, str]:
    """(titulo, mensaje) de una sospecha descartada."""
    return ("Sospecha descartada", f"Sospecha descartada · {ubicacion(cama)} · posición {posicion}.")


def ventilacion(cama, horas) -> tuple[str, str]:
    """(titulo, mensaje) del apagado automático de la ventilación."""
    return ("Ventilación apagada",
            f"Ventilación de B{cama['bloque']} · Nave {cama['nave']} apagada {horas} h "
            f"(las esporas viajan con el aire). Origen: {ubicacion(cama)}.")


def seguimiento(cama, resultado, afectadas) -> tuple[str, str]:
    """(titulo, mensaje) de una revisita del robot."""
    return (f"Seguimiento: {resultado}",
            f"Revisita {ubicacion(cama)}: {resultado}, {_plantas(afectadas)}.")

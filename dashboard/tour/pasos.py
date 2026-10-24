"""Pasos del tour guiado del pitch. Los textos viven SOLO aquí: edítalos sin tocar el motor.

Cada paso: titulo (≤ 6 palabras), texto (≤ 2 líneas, ~25 palabras), target (selector CSS del elemento destacado:
`.st-key-<clave>` de un st.container o `[data-tour=...]` del HTML; None = recuadro centrado), cerca (opcional: sube del
target al ancestro que cumpla ese selector), hito (dashboard/tour/hitos.py: el tour avanza la simulación hasta que
ocurre), accion (dashboard/tour/acciones.py: pantalla que se abre) y permitir_interaccion (clics sobre el destacado).
"""
from collections.abc import Callable
from dataclasses import dataclass

from dashboard.tour import acciones as A
from dashboard.tour import hitos as H

FOCO = "B1-N2-C14"          # config/demo.yaml · enfermedad.focos_forzados
NAVE_FOCO = (1, 2)          # bloque y nave del foco (la de ventilación controlable en la demo)
HR_HUMEDA = 98.0            # fuente: supuesto · lectura claramente húmeda: la noche del evento forzado de config/demo.yaml


@dataclass(frozen=True)
class Paso:
    """Un paso del tour."""
    id: str
    titulo: str
    texto: str
    target: str | None = None
    cerca: str | None = None
    hito: Callable | None = None
    accion: Callable | None = None
    permitir_interaccion: bool = False


PASOS = [
    Paso("bienvenida", "Atalaya",
         "Detecta Botrytis, mildiú polvoso, Neofusicoccum y Phytophthora antes de que se vean. Veamos unos días del invernadero.",
         accion=A.pantalla("finca")),
    Paso("mapa", "Mapa de la finca",
         "Cada cama de la finca, con su nombre real: Bloque · Nave · Cama.",
         target=".st-key-tour_mapa", hito=H.riesgo(nivel="%"), accion=A.pantalla("finca")),
    Paso("microclima", "Microclima por cama",
         "El robot mide temperatura y humedad en cada cama, incluso en las esquinas. Esta noche la Nave 2 se satura.",
         target=".st-key-tour_mapa", hito=H.lectura("robot:%", "B1-N2-%", HR_HUMEDA),
         accion=A.pantalla("finca", capa="humedad")),
    Paso("prediccion", "Predicción a 7 días",
         "La IA predice alto riesgo en esta cama para los próximos 7 días.",
         target='[data-tour="riesgo"]', hito=H.riesgo(FOCO, "alto"), accion=A.cama(FOCO)),
    Paso("alerta", "Alerta de riesgo",
         "El agrónomo recibe la alerta con la causa: humedad alta durante muchas horas.",
         target=f'[data-tour="alerta-riesgo_7d-{FOCO}"]', cerca='[class*="st-key-acard_"]',
         hito=H.alerta("riesgo_7d", FOCO), accion=A.alerta("riesgo_7d", FOCO)),
    Paso("prioriza", "El robot prioriza",
         "El robot deja su patrulla y va primero a la cama de mayor riesgo.",
         target=".st-key-tour_robot", hito=H.robot("prioridad", FOCO), accion=A.pantalla("finca")),
    Paso("inspeccion", "Inspección dentro del follaje",
         "Baja la cámara 360 entre las plantas sin tocarlas.",
         target=".st-key-tour_mapa", hito=H.robot("inspeccionando", FOCO), accion=A.pantalla("finca")),
    Paso("confirmacion", "Botrytis confirmada",
         "Cama, posición y plantas afectadas: el robot lo registra solo.",
         target=".st-key-card_det", hito=H.incidencia("confirmada", FOCO), accion=A.incidencia(FOCO)),
    Paso("ventilacion", "Contener el contagio",
         "Las esporas viajan con el aire: se apaga la ventilación de la nave.",
         target=f'[data-tour="vent-B{NAVE_FOCO[0]}-N{NAVE_FOCO[1]}"]', hito=H.ventilacion("apagada", *NAVE_FOCO),
         accion=A.ventilacion(NAVE_FOCO[0])),
    Paso("seguimiento", "Seguimiento automático",
         "El robot vuelve a revisar y registra si mejora o empeora.",
         target=".st-key-card_det", hito=H.seguimiento(), accion=A.incidencia(FOCO)),
    Paso("sin_red", "Sin internet",
         "Sin red, un celular descarga los datos del robot y los sincroniza después.",
         target=".st-key-pie", accion=A.sin_red(), permitir_interaccion=True),
    Paso("cierre", "Predecir, detectar, seguir",
         "Predecir, detectar y hacer seguimiento, todo sin internet.",
         accion=A.pantalla("finca")),
]

"""Las 6 gráficas para las slides (PNG 1920×1080, fondo oscuro) a partir de data/resultados/."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, precision_recall_curve, roc_auc_score, roc_curve

from sim.config import RAIZ, cargar_config

RESULTADOS = RAIZ / "data" / "resultados"
FONDO, TEXTO, REJILLA = "#0f172a", "#e2e8f0", "#334155"
COLORES = {"actual": "#94a3b8", "sensor_central": "#fbbf24", "drones": "#34d399",
           "drones_celular": "#60a5fa", "drones_sin_vent": "#f472b6",
           "reglas": "#fbbf24", "IA": "#34d399", "IA solo sensor central": "#f87171"}
NOMBRES = {"actual": "Actual\n(sensor + ronda manual)", "sensor_central": "Sensor central\n+ modelo", "drones": "Drones\n(nuestra solución)",
           "drones_celular": "Drones\nsin internet (celular)", "drones_sin_vent": "Drones sin apagar\nventilación"}
ESCENARIOS = list(NOMBRES)


def _figura(titulo: str, subtitulo: str = ""):
    """Figura 1920×1080 con fondo oscuro y título."""
    plt.rcParams.update({"text.color": TEXTO, "axes.labelcolor": TEXTO, "xtick.color": TEXTO, "ytick.color": TEXTO,
                         "axes.edgecolor": REJILLA, "font.size": 18, "font.family": "DejaVu Sans"})
    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=FONDO)
    fig.suptitle(titulo, fontsize=34, fontweight="bold", color=TEXTO, y=0.98)
    if subtitulo:
        fig.text(0.5, 0.885, subtitulo, ha="center", fontsize=19, color="#94a3b8")
    return fig


def _eje(fig, *pos):
    """Eje con fondo oscuro y rejilla suave."""
    ax = fig.add_axes(pos, facecolor=FONDO)
    ax.grid(color=REJILLA, alpha=0.6, linewidth=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    return ax


def _guardar(fig, nombre: str) -> None:
    fig.savefig(RESULTADOS / nombre, facecolor=FONDO)
    plt.close(fig)


def g1_anticipacion(df: pd.DataFrame) -> None:
    """Días de anticipación por escenario (cajas, una observación por semilla)."""
    fig = _figura("Días de anticipación por escenario", "Positivo = avisamos antes de que la enfermedad se vea · una caja por escenario, un punto por semilla")
    ax = _eje(fig, 0.07, 0.17, 0.90, 0.66)
    datos = [df.loc[df.escenario == e, "anticipacion_dias"].dropna().to_numpy() for e in ESCENARIOS]
    caja = ax.boxplot(datos, patch_artist=True, widths=0.55, medianprops={"color": FONDO, "linewidth": 3})
    rng = np.random.default_rng(0)
    for i, (e, d) in enumerate(zip(ESCENARIOS, datos), start=1):
        caja["boxes"][i - 1].set(facecolor=COLORES[e], edgecolor=COLORES[e], alpha=0.85)
        for k in ("whiskers", "caps"):
            for ln in caja[k][2 * (i - 1):2 * i]:
                ln.set(color=COLORES[e])
        ax.scatter(i + rng.uniform(-0.15, 0.15, d.size), d, s=26, color=TEXTO, alpha=0.55, zorder=3)
        ax.text(i, ax.get_ylim()[1] * 0.97, f"{np.mean(d):.1f} d", ha="center", va="top", fontsize=22, color=COLORES[e], fontweight="bold")
    ax.axhline(0, color="#f87171", linewidth=2, linestyle="--")
    cobertura = {e: g.camas_avisadas_antes.sum() / max(g.camas_infectadas.sum(), 1) for e, g in df.groupby("escenario")}
    ax.set_xticks(range(1, len(ESCENARIOS) + 1),
                  [f"{NOMBRES[e]}\navisó antes en el {cobertura[e]:.0%}\nde las camas infectadas" for e in ESCENARIOS], fontsize=16)
    ax.set_ylabel("días entre el aviso y los primeros síntomas\n(o los que habrían aparecido)")
    _guardar(fig, "1_anticipacion.png")


def g2_afectadas(series: pd.DataFrame) -> None:
    """Plantas afectadas en el tiempo: actual vs. drones (media ± IC 95 %)."""
    fig = _figura("Plantas afectadas durante la temporada", "Media de las semillas ± IC 95 % · latentes + con síntomas + perdidas")
    ax = _eje(fig, 0.07, 0.12, 0.90, 0.70)
    for e in ("actual", "drones"):
        s = series[series.escenario == e].pivot(index="dia", columns="semilla", values="afectadas") * 100
        m, se = s.mean(axis=1), s.std(axis=1, ddof=1) / np.sqrt(s.shape[1])
        ax.plot(s.index, m, color=COLORES[e], linewidth=4, label=NOMBRES[e].replace("\n", " "))
        ax.fill_between(s.index, m - 1.96 * se, m + 1.96 * se, color=COLORES[e], alpha=0.25)
        ax.text(s.index[-1] + 0.5, m.iloc[-1], f"{m.iloc[-1]:.1f} %", color=COLORES[e], fontsize=24, fontweight="bold", va="center")
    ax.set_xlabel("día de la temporada")
    ax.set_ylabel("% de plantas afectadas")
    ax.legend(frameon=False, fontsize=22, loc="upper left")
    ax.set_xlim(1, series.dia.max() + 6)
    _guardar(fig, "2_afectadas_tiempo.png")


def g3_curvas(riesgo: pd.DataFrame) -> None:
    """ROC y PR: reglas vs. IA vs. IA solo con sensor central."""
    fig = _figura("¿Qué tan bien ordena el riesgo cada modelo?", "Semillas de validación (nunca vistas en el entrenamiento) · riesgo de infección a 7 días por cama y día")
    ax_roc, ax_pr = _eje(fig, 0.06, 0.12, 0.41, 0.70), _eje(fig, 0.55, 0.12, 0.41, 0.70)
    d, c = riesgo[riesgo.escenario == "drones"], riesgo[riesgo.escenario == "sensor_central"]
    for nombre, datos, col in (("reglas", d, "reglas"), ("IA", d, "prob"), ("IA solo sensor central", c, "prob")):
        y, p = datos["y"].to_numpy(), datos[col].to_numpy()
        fpr, tpr, _ = roc_curve(y, p)
        pre, rec, _ = precision_recall_curve(y, p)
        ax_roc.plot(fpr, tpr, color=COLORES[nombre], linewidth=4, label=f"{nombre} · AUC {roc_auc_score(y, p):.2f}")
        ax_pr.plot(rec, pre, color=COLORES[nombre], linewidth=4, label=f"{nombre} · PR-AUC {average_precision_score(y, p):.2f}")
    ax_roc.plot([0, 1], [0, 1], color="#64748b", linestyle="--", linewidth=2)
    ax_roc.set(xlabel="falsos positivos", ylabel="aciertos (sensibilidad)", title="Curva ROC")
    ax_pr.set(xlabel="sensibilidad", ylabel="precisión", title="Curva precisión-sensibilidad")
    for ax in (ax_roc, ax_pr):
        ax.legend(frameon=False, fontsize=18, loc="lower right" if ax is ax_roc else "upper right")
        ax.title.set_fontsize(24)
    _guardar(fig, "3_curvas_modelo.png")


def g4_importancia() -> None:
    """Importancia de variables por permutación (modelo completo)."""
    imp = pd.read_csv(RESULTADOS / "importancia.csv", encoding="utf-8")
    imp = imp[imp.variante == "completo"].sort_values("importancia").tail(10)
    fig = _figura("¿En qué se fija la IA?", "Importancia por permutación · caída del AUC al barajar cada variable (semillas de prueba)")
    ax = _eje(fig, 0.26, 0.12, 0.70, 0.70)
    ax.barh(imp.variable, imp.importancia, xerr=imp.desvio, color=COLORES["IA"], ecolor=TEXTO, height=0.65)
    ax.set_xlabel("caída del AUC")
    _guardar(fig, "4_importancia_variables.png")


def g5_errores(df: pd.DataFrame) -> None:
    """Tabla de aciertos, falsas alarmas y focos no detectados por escenario (media por temporada)."""
    fig = _figura("Aciertos y errores por escenario", "Media por temporada (30 semillas)")
    ax = fig.add_axes([0.03, 0.12, 0.94, 0.68], facecolor=FONDO)
    ax.axis("off")
    cols = [("confirmaciones", "Confirmaciones\n(aciertos)"), ("confirmaciones_falsas", "Confirmaciones\nfalsas"),
            ("descartadas", "Sospechas\ndescartadas"), ("alertas_alto_falsas", "Alertas alto sin\ninfección en 7 d"),
            ("focos_no_detectados", "Focos no\ndetectados"), ("plantas_perdidas", "Plantas\nperdidas")]
    g = df.groupby("escenario").mean(numeric_only=True).loc[ESCENARIOS]
    celdas = [[NOMBRES[e].replace("\n", " ")] + [f"{g.loc[e, k]:.1f}" for k, _ in cols] for e in ESCENARIOS]
    ancho = [0.28] + [0.12] * len(cols)
    tabla = ax.table(cellText=celdas, colLabels=["Escenario"] + [n for _, n in cols], colWidths=ancho,
                     bbox=[0, 0, 1, 1], cellLoc="center")
    tabla.auto_set_font_size(False)
    tabla.set_fontsize(19)
    for (fila, col), celda in tabla.get_celld().items():
        celda.set_facecolor(FONDO if fila else "#1e293b")
        celda.set_edgecolor(REJILLA)
        celda.get_text().set_color(COLORES[ESCENARIOS[fila - 1]] if fila and col == 0 else TEXTO)
        if col == 0:
            celda.get_text().set_ha("left")
            celda.PAD = 0.04
    _guardar(fig, "5_tabla_errores.png")


def g6_red_vs_celular(df: pd.DataFrame) -> None:
    """Anticipación con red local vs. con celular (pareada por semilla)."""
    fig = _figura("Costo del peor caso: sin internet", "Misma semilla, red local vs. celular que pasa una vez al día (7-15 h) · días de anticipación")
    ax = _eje(fig, 0.07, 0.12, 0.90, 0.70)
    p = df.pivot(index="semilla", columns="escenario", values="anticipacion_dias")[["drones", "drones_celular"]].dropna()
    for _, f in p.iterrows():
        ax.plot([1, 2], [f["drones"], f["drones_celular"]], color="#64748b", alpha=0.5, linewidth=1.5, zorder=1)
    for i, e in enumerate(("drones", "drones_celular"), start=1):
        ax.scatter(np.full(len(p), i), p[e], s=60, color=COLORES[e], zorder=3)
        ax.plot([i - 0.2, i + 0.2], [p[e].mean()] * 2, color=COLORES[e], linewidth=6, zorder=4)
        ax.text(i + 0.25, p[e].mean(), f"{p[e].mean():.1f} d", color=COLORES[e], fontsize=26, fontweight="bold", va="center")
    dif = (p["drones"] - p["drones_celular"]).mean()
    ax.set_title(f"Se pierden {dif:.1f} días de anticipación en promedio, pero seguimos avisando antes" if dif > 0
                 else f"Diferencia media: {dif:.1f} días (el celular no cambia la anticipación de forma apreciable)", fontsize=22, pad=14)
    ax.set_xticks([1, 2], [NOMBRES["drones"], NOMBRES["drones_celular"]])
    ax.set_xlim(0.5, 2.7)
    ax.set_ylabel("días de anticipación")
    q = df.pivot(index="semilla", columns="escenario", values=["retraso_deteccion_dias", "afectadas_final", "plantas_perdidas"])
    d_ret = (q["retraso_deteccion_dias"]["drones_celular"] - q["retraso_deteccion_dias"]["drones"]).mean()
    d_af = (q["afectadas_final"]["drones_celular"] - q["afectadas_final"]["drones"]).mean() * 100
    fig.text(0.5, 0.04, f"Lo que sí cuesta no tener red: la confirmación tarda {d_ret:+.1f} días más y termina {d_af:+.2f} puntos más de plantas afectadas",
             ha="center", fontsize=20, color="#94a3b8")
    _guardar(fig, "6_red_local_vs_celular.png")


def main() -> None:
    """Genera las 6 gráficas en data/resultados/."""
    cargar_config()                                          # valida la config antes de graficar
    df = pd.read_parquet(RESULTADOS / "metricas.parquet")
    series = pd.read_parquet(RESULTADOS / "series_afectadas.parquet")
    riesgo = pd.read_parquet(RESULTADOS / "riesgo_validacion.parquet")
    g1_anticipacion(df)
    g2_afectadas(series)
    g3_curvas(riesgo)
    g4_importancia()
    g5_errores(df)
    g6_red_vs_celular(df)
    print(f"6 gráficas en {RESULTADOS}")


if __name__ == "__main__":
    main()

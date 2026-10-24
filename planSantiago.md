# planSantiago.md · Simulador, modelo predictivo y validación

Dueño: **Santiago** (Ing. Matemática). Carpetas: `sim/`, `prediccion/`, `analisis/`.
Lee primero `CLAUDE.md` (contrato de datos y convenciones).

**Objetivo:** un simulador de invernadero con drones de cable que genere datos realistas, un modelo que prediga infección por cama a 7 días, y evidencia numérica de que el sistema detecta antes que la práctica actual.

**Regla de oro:** primero que todo corra de punta a punta con valores simples; después se afina.

---

## Fase 1 · Base y contrato (22:00–23:30)

1. **Contrato de datos con Samuel**
   - Revisar juntos `contrato/schema.sql` (en `CLAUDE.md`) y congelarlo.
   - Acordar quién escribe qué: yo escribo `corridas`, `camas`, `lecturas`, `riesgo`, `incidencias`, `seguimientos`, `drones`, `ventilacion` y `cola_sync`. Samuel lee todo y escribe el estado y la acción de las alertas.
2. **Parámetros biológicos con Sara B.** (Botrytis primero). Pasarlos a `config/default.yaml`:
   - Rango de temperatura favorable y óptimo.
   - Humedad relativa que cuenta como “mojado” y horas de mojado para riesgo alto.
   - Días de latencia (contagia sin síntomas) y días hasta pérdida sin tratamiento.
   - Dónde aparecen síntomas (afecta la probabilidad de que la cámara los vea).
   - Si no llegan a tiempo: dejar los valores supuestos de abajo marcados como `# fuente: supuesto`.
3. **Esqueleto del repo:** `sim/`, `prediccion/`, `analisis/`, `config/default.yaml`, `sim/escritor.py` que crea la base con `contrato/schema.sql`.

**Listo cuando:** `python -m sim.run_temporada --dias 1` crea `data/finca.db` con las tablas vacías y la tabla `camas` llena.

---

## Fase 2 · Simulador del invernadero (23:30–01:30)

### 2.1 Geometría · `sim/geometria.py`
- 4 bloques × 6 naves × 12 camas × 40 plantas (configurable). Camas numeradas continuas dentro del bloque.
- Índice global de planta `i` y arreglos: `bloque[i]`, `nave[i]`, `cama[i]`, `posicion[i]`.
- `es_borde` (por cama, el del contrato): primera y última cama de cada nave. Se escribe en `camas` y es variable del modelo.
- `es_borde_planta` (por planta, solo interno en `sim/`): cama de borde **o** posiciones 1–5 y 36–40 (esquinas). Nunca va a la base.
- **Vecindad** (matriz dispersa, una vez): misma cama a ±2 posiciones (peso 1.0) y camas contiguas de la misma nave a ±1 posición (peso 0.4).
- **Corriente de aire:** la ventilación sopla a lo largo de la nave en un sentido fijo. Una planta infecciosa aporta presión a las camas “aguas abajo” de su nave, decayendo con la distancia: `w_aire = exp(-d / L_aire)`.

### 2.2 Clima por cama · `sim/clima.py`
Por hora `h` (hora del día `h % 24`) y por cama:
- `T = T_media + A_T·sin(2π(h−9)/24) + offset_nave + ruido`
- `HR = HR_media − A_HR·sin(2π(h−9)/24) + offset_nave + extra_borde·es_borde + ruido`, recortada a [30, 100].
- **Eventos húmedos:** aleatorios (tasa por día), duran 6–18 h, suben la HR del bloque.
- **Ventilación encendida:** baja la HR de la nave (`−Δ_vent`) pero activa la corriente de aire. Apagada: sube la HR, no hay transporte de esporas. Esto crea un dilema real que vale la pena mostrar.
- **Horas de mojado:** acumulado de horas con `HR ≥ umbral_mojado` en ventanas de 24 h y 72 h.
- Guardar `T`, `HR` y mojado verdaderos por cama y hora en memoria (numpy).

### 2.3 Enfermedad · `sim/enfermedad.py` (vectorizado)
Estados por planta: `0 sana · 1 latente (contagia, sin síntomas) · 2 con síntomas · 3 tratada · 4 perdida`.

Probabilidad de infección por hora para una planta sana:

```
f_T  = exp(-((T - T_opt) / T_ancho)^2)
f_M  = min(1, horas_mojado_24h / horas_mojado_full)
p    = 1 - exp(-(β_vec·presion_vecinos + β_aire·presion_aire + β_0) · f_T · f_M)
```

- `presion_vecinos = V @ (0.5·[latente] + 1.0·[síntomas])`
- `presion_aire` solo si la ventilación de la nave está encendida.
- Latente → síntomas tras `U(latencia_min, latencia_max)` días. Síntomas → perdida si no se trata.
- `tratar(plantas)`: éxito con probabilidad `eficacia`, pasa a tratada (deja de contagiar), vuelve a sana tras `dias_proteccion`.
- Semillas de infección: 1–3 focos por temporada en plantas aleatorias (preferir `es_borde_planta`).

**Calibrar `β`:** en el escenario `sensor_central`, la temporada debe terminar con 5–15 % de plantas afectadas. Hacer un barrido rápido de `β_vec` y `β_aire`.

### 2.4 Sensores fijos · `sim/sensores.py`
- Escenario `sensor_central`: un sensor por bloque en la cama central. Mide `T` y `HR` de esa cama con ruido cada hora. Para las demás camas, el sistema solo “sabe” ese valor.
- Escribe en `lecturas` con `fuente='sensor_fijo'`.

**Listo cuando:** una temporada de 60 días corre en menos de 60 s y genera focos que crecen y se expanden por la nave.

---

## Fase 3 · Modelo predictivo (01:30–03:30)

### 3.1 Qué sabe el sistema (sin trampa) · `prediccion/variables.py`
Las variables se calculan **solo con lo que la finca conocería**: lecturas (sensor fijo o dron) e incidencias confirmadas. **Nunca** con el estado real de las plantas.

Para cada cama, cada día a las 06:00:
- `temp_media_24h`, `temp_min_24h`, `temp_max_24h`
- `hr_media_24h`, `hr_max_24h`, `delta_hr_24h` (cambio contra el día anterior)
- `horas_mojado_24h`, `horas_mojado_72h`, `dias_seguidos_hr_alta`
- `confirmadas_misma_cama`, `confirmadas_camas_vecinas`, `distancia_a_confirmada_en_nave` (en camas; 99 si no hay)
- `ventilacion_encendida`, `es_borde`
- `edad_lectura_h` (horas desde la última medición real de esa cama; alta si solo hay sensor central)

### 3.2 Etiqueta · `prediccion/etiquetas.py`
`y = 1` si alguna planta de la cama pasa de sana a latente en los próximos 7 días (168 h). Se calcula con la verdad del simulador, solo para entrenar y evaluar.

### 3.3 Línea base: reglas biológicas · `prediccion/reglas.py`
`riesgo_reglas = f_T(temp_media_24h) · min(1, horas_mojado_72h / umbral) · (1 + bonus si hay confirmadas cerca)`, recortado a [0, 1]. Es lo que haría un agrónomo con una tabla; sirve para comparar.

### 3.4 Modelo de IA · `prediccion/ia.py`, `prediccion/entrenar.py`
- `HistGradientBoostingClassifier` de scikit-learn (sin dependencias extra). LightGBM solo si ya está instalado.
- Datos: 40 temporadas simuladas (semillas 0–39) para entrenar, 10 (40–49) para probar. **Se separa por temporada**, no por fila, para no filtrar información.
- Clases desbalanceadas: `class_weight='balanced'` o pesos por muestra.
- Guardar el modelo en `data/modelo_ia.joblib` y la lista de variables en `data/modelo_ia.json`.
- Importancia de variables (permutación) para la slide de IA.

### 3.5 Escritura del riesgo
Cada día a las 06:00 el simulador calcula `riesgo_reglas` y `prob_ia_7d` por cama, asigna `nivel` y escribe en `riesgo`. Si el nivel pasa a `alto`, crea una alerta `riesgo_7d` (severidad `advertencia`):
`B1 · Nave 2 · Cama 14: alto riesgo de Botrytis en los próximos 7 días (prob. 0.74). HR > 90 % durante 15 h.`

**Listo cuando:** `python -m prediccion.entrenar` imprime AUC y PR-AUC de reglas vs. IA en las semillas de prueba.

---

## Descanso (03:30–06:30)

Antes de parar: entregar a Samuel un `data/finca.db` **parcial** (clima, lecturas, riesgo, alertas; sin drones). Acordado en `NOTAS.md`.

---

## Fase 4 · Drones de cable y seguimiento (06:30–08:00) · `sim/drones.py`

Un dron por bloque. Estados: `patrulla → prioridad → inspeccionando → carga`.

- **Patrulla rutinaria:** recorre las camas del bloque en orden (1 → 72 → 1…). Tiempo por cama: `min_por_cama` (por defecto 6 min, incluye bajar la cámara en varios puntos). En cada cama:
  - Mide `T` y `HR` de esa cama (con ruido) → `lecturas` con `fuente='dron:B{n}'`. **Así el dron reemplaza los sensores que faltan.**
  - Inspecciona: cada planta latente se detecta con `sens_latente` (baja, ej. 0.25), con síntomas con `sens_sintomas` (ej. 0.9); falsos positivos con `1 − especificidad`.
- **Prioridad:** si una cama de su bloque tiene `nivel='alto'` y no se visitó en las últimas 24 h, el dron interrumpe la patrulla y va ahí primero (cola ordenada por `prob_ia_7d`).
- **Hallazgo:** crea incidencia `sospecha` → si la inspección da positivo, `confirmada` + alerta `critica`:
  `Botrytis confirmada · B1 · Nave 2 · Cama 14 · posición 22. 3 plantas afectadas (confianza 0.88).`
  Si da negativo: `descartada` + alerta `info`.
- **Ventilación:** si se confirma en una nave con `tiene_ventilacion=1`, apagarla 48 h → `ventilacion` + alerta `ventilacion`.
- **Tratamiento:** el personal trata la zona `horas_hasta_tratamiento` después (por defecto 6 h) → `en_tratamiento`.
- **Seguimiento automático:** el dron vuelve cada `dias_revisita` (por defecto 3) y escribe en `seguimientos` el resultado (`empeora`, `igual`, `mejora`, `limpia`). Dos revisitas `limpia` seguidas → `cerrada`. Si `empeora` → vuelve a `confirmada` y se trata de nuevo.
- Escribir la posición del dron en `drones` en cada cambio de cama (para que el dashboard lo anime).
- Batería: baja por hora de trabajo; a `bateria_min` va a cargar `horas_carga`.

**Listo cuando:** en una temporada `drones` hay incidencias en todos los estados y seguimientos registrados solos.

---

## Fase 5 · Escenarios y validación (08:00–10:30) · `analisis/`

### 5.1 Escenarios (misma semilla para todos: números aleatorios comunes)
| Escenario | Qué tiene |
|---|---|
| `actual` | Sensor central + revisión manual (prob. de ver síntomas `p_humano` por pasada, una pasada por cama cada `dias_ronda`). Sin predicción. |
| `sensor_central` | Sensor central + modelo predictivo + dron que solo va cuando hay alerta. |
| `drones` | Drones patrullando y midiendo + modelo + prioridad + seguimiento. **Nuestra solución.** |
| `drones_celular` | Igual que `drones`, pero sin red: los datos llegan al modelo solo cuando un trabajador pasa con el celular (una vez al día, hora aleatoria entre 7 y 15 h). Usa `cola_sync`. |
| `drones_sin_vent` | `drones` sin apagar la ventilación (para medir el aporte de ese control). |

### 5.2 Métricas · `analisis/metricas.py`
- **Días de anticipación:** por cada foco, (día de los primeros síntomas) − (día de la primera alerta `alto` o confirmación en esa cama). Positivo = avisamos antes de que se vea.
- **Retraso de detección:** día de confirmación − día real de infección del primer caso de la cama.
- **Plantas afectadas** al final de la temporada (latentes + síntomas + perdidas) y en el pico.
- **Falsas alarmas:** alertas `alto` sin infección en los 7 días siguientes; incidencias `descartada`.
- **Focos no detectados:** camas con ≥ 5 plantas con síntomas que nunca se confirmaron a tiempo.
- **Modelo:** AUC, PR-AUC y aciertos en el top-10 de camas por día (lo que el dron alcanza a visitar), reglas vs. IA vs. IA solo con sensor central.
- **Costo del peor caso:** cuántos días de anticipación se pierden en `drones_celular` frente a `drones`.

### 5.3 Corridas
`python -m analisis.validar --semillas 30` → `data/resultados/metricas.parquet`. Reportar media e intervalo de confianza del 95 % (bootstrap) y diferencias pareadas por semilla.

### 5.4 Gráficas para las slides · `analisis/graficas.py` (PNG 1920×1080, fondo oscuro)
1. Días de anticipación por escenario (cajas).
2. Plantas afectadas en el tiempo, `actual` vs. `drones` (media ± IC).
3. Curva ROC/PR: reglas vs. IA vs. IA solo con sensor central.
4. Importancia de variables del modelo.
5. Tabla de errores: aciertos, falsas alarmas, no detectados.
6. Anticipación con red local vs. con celular.

**Casos donde falla (mostrarlos, el jurado lo valora):** periodos secos con contagio por aire; latentes que la cámara no ve; muchos focos a la vez con un solo dron por bloque.

---

## Fase 6 · Demo y cierre (10:30–12:00)

1. **Escenario de demo** `config/demo.yaml`: Bloque 1, foco latente sembrado en Nave 2 · Cama 14 el día 1; evento húmedo la noche del día 2; ventilación encendida en la Nave 2.
   Secuencia esperada en ~3 minutos de demo: alerta de riesgo a 7 días → el dron cambia de patrulla a prioridad → inspecciona → confirmada → ventilación apagada (automática, con alerta) → seguimiento automático 3 días después → `mejora` → modo *Sin red* (`run_vivo` escribe `cola_sync`; Samuel muestra *Pasa el celular*).
2. **A las 09:30** (acordado en `NOTAS.md`, adelantar este punto) entregar a Samuel el comando `python -m sim.run_vivo --config config/demo.yaml --velocidad 1` (1 hora simulada por segundo) y verificar con él que el dashboard lo muestra.
3. Slides de evidencia e IA con Sara D. Mensajes:
   - “Avisamos X días antes de que la enfermedad se vea.”
   - “La IA acierta más que las reglas, sobre todo en camas de borde que el sensor central no ve.”
   - “Sin internet perdemos Y días de anticipación, pero seguimos avisando antes.”
4. Preparar dos respuestas para el jurado:
   - **¿Por qué IA y no solo reglas?** Por la interacción no lineal entre humedad, temperatura, cambios bruscos y vecinos, y porque aprende de la finca con cada temporada.
   - **¿Qué tan reales son los datos?** Son simulados, con parámetros de literatura revisados por la bióloga. El siguiente paso es calibrarlos con lecturas reales de un piloto.

**11:30 código congelado.**

---

## Parámetros iniciales (`config/default.yaml`) · reemplazar con los de Sara B.

```yaml
semilla: 7
sim: {dias: 60, inicio: "2026-11-01T00:00:00"}
geometria: {bloques: 4, naves_por_bloque: 6, camas_por_nave: 12, plantas_por_cama: 40}
clima:
  T_media: 18.0            # fuente: supuesto (invernadero en altiplano)
  A_T: 6.0
  HR_media: 78.0
  A_HR: 10.0
  extra_borde_hr: 4.0       # esquinas y bordes más húmedos
  delta_ventilacion_hr: -5.0
  eventos_humedos_por_dia: 0.15
  umbral_mojado_hr: 90.0
enfermedad:                 # botrytis, fuente: supuesto hasta recibir datos de Sara B.
  T_opt: 18.0
  T_ancho: 6.0
  horas_mojado_full: 10
  beta_vec: 0.05
  beta_aire: 0.02
  beta_0: 2.0e-6
  L_aire_camas: 3.0
  latencia_dias: [7, 14]
  sintomas_a_perdida_dias: [14, 28]
  eficacia_tratamiento: 0.85
  dias_proteccion: 4
  focos_por_temporada: [1, 3]
drones:
  por_bloque: 1
  min_por_cama: 6
  sens_latente: 0.25
  sens_sintomas: 0.90
  especificidad: 0.98
  dias_revisita: 3
  horas_hasta_tratamiento: 6
  bateria_horas: 6
  horas_carga: 1
riesgo: {umbral_alto: 0.6, umbral_medio: 0.3}
actual: {p_humano: 0.35, dias_ronda: 4}
```

---

## Si voy tarde: qué cortar (en este orden)

1. Una sola enfermedad (Botrytis).
2. Batería de los drones.
3. Escenario `drones_sin_vent`.
4. Bajar a 15 semillas.

**Nunca cortar:** la predicción a 7 días con la IA comparada contra las reglas, los drones con patrulla y prioridad, el seguimiento automático, el escenario `drones_celular` y la gráfica de anticipación con sus errores.

---

## Checklist de entrega a Samuel

- [ ] `data/finca.db` de una temporada `drones` con todas las tablas llenas (para que construya el dashboard).
- [ ] `run_vivo` escribiendo hora a hora sin bloquear la lectura (SQLite en modo WAL).
- [ ] Escenario `demo` que produce la secuencia completa en menos de 3 minutos.
- [ ] Gráficas en `data/resultados/` para la pestaña de evidencia.

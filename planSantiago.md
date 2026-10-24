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
2. **Parámetros biológicos de Sara B.: recibidos** (`Scientificic information.pdf`) y ya pasados a `config/default.yaml`:
   - Clima del altiplano 12–18 °C, HR > 70 %. Óptimo de Botrytis 16–20 °C, germina de 5 a 30 °C.
   - Mojado: HR ≥ 95 % (Broome), una pausa seca > 4 h reinicia el conteo; el riego también moja.
   - Factor ambiental: Nair y Allen (1993); reglas: índice de Broome (1995); dispersión: núcleo exponencial (b = 0,5/m, camas a 1,8 m).
   - Latencia **no verificada en arándano** → sigue como supuesto (el PDF usa 14 días en su ejemplo).
   - Síntomas: moho gris-pardo en flores y frutos; entra por flores senescentes, frutos maduros y heridas.
   - Lo que sigue como `# fuente: supuesto` está marcado así en el YAML; decláralo en el pitch.
3. **Esqueleto del repo:** `sim/`, `prediccion/`, `analisis/`, `config/default.yaml`, `sim/escritor.py` que crea la base con `contrato/schema.sql`.

**Listo cuando:** `python -m sim.run_temporada --dias 1` crea `data/finca.db` con las tablas vacías y la tabla `camas` llena.

---

## Fase 2 · Simulador del invernadero (23:30–01:30)

### 2.1 Geometría · `sim/geometria.py`
- 4 bloques × 6 naves × 12 camas × 40 plantas (configurable). Camas numeradas continuas dentro del bloque.
- Índice global de planta `i` y arreglos: `bloque[i]`, `nave[i]`, `cama[i]`, `posicion[i]`.
- `es_borde` (por cama, el del contrato): primera y última cama de cada nave. Se escribe en `camas` y es variable del modelo.
- `es_borde_planta` (por planta, solo interno en `sim/`): cama de borde **o** posiciones 1–5 y 36–40 (esquinas). Nunca va a la base.
- **Vecindad** (matriz dispersa, una vez) con el **núcleo exponencial del PDF**: `K(d) = exp(−b·d)`, `b = 0,5 /m`, `d` en metros entre plantas (misma cama: `Δposición · separacion_plantas_m`; camas contiguas de la misma nave: `√(1,8² + (Δposición·sep)²)`). Pesos `< corte_nucleo` se descartan. Referencia: cama contigua misma posición 0,41; dos camas 0,17; misma cama ±1 posición 0,78.
- **Corriente de aire:** la ventilación sopla a lo largo de la nave en un sentido fijo. Una planta infecciosa aporta presión a las camas “aguas abajo” de su nave, decayendo con la distancia: `w_aire = exp(-d / L_aire)`. (PDF: los conidios viajan por aire y Botrytis es de las que más salta entre camas.)

### 2.2 Clima por cama · `sim/clima.py`
Por hora `h` (hora del día `h % 24`) y por cama:
- `T = T_media + A_T·sin(2π(h−9)/24) + offset_nave + ruido`
- `HR = HR_media − A_HR·sin(2π(h−9)/24) + offset_nave + extra_borde·es_borde + ruido`, recortada a [30, 100].
- **Eventos húmedos:** aleatorios (tasa por día), duran 6–18 h, suben la HR del bloque.
- **Ventilación encendida:** baja la HR de la nave (`−Δ_vent`) pero activa la corriente de aire. Apagada: sube la HR, no hay transporte de esporas. Esto crea un dilema real que vale la pena mostrar.
- **Mojado (regla de Broome, PDF):** una hora está mojada si `HR ≥ mojado.umbral_hr` (95 %) **o** es hora de riego (`mojado.riego_horas`). `W` = duración del periodo mojado actual; se reinicia solo si hay **más de 4 h secas seguidas** (`pausa_seca_reinicio_h`). También: horas mojadas en ventanas de 24 h y 72 h.
- **Punto de rocío (Magnus, PDF):** `γ = ln(HR/100) + a·T/(b + T)`, `Td = b·γ/(a − γ)`, con `a = 17,62`, `b = 243,12`. Sirve como variable (`T − Td`).
- Guardar `T`, `HR` y mojado verdaderos por cama y hora en memoria (numpy).

### 2.3 Enfermedad · `sim/enfermedad.py` (vectorizado)
Estados por planta: `0 sana · 1 latente (contagia, sin síntomas) · 2 con síntomas · 3 tratada · 4 perdida`.

Probabilidad de infección por hora para una planta sana:

Es el modelo espacial estocástico del PDF (`p = 1 − exp(−λ·Δt)`, `λ = β · f_ambiental · Σ I_j·K(d_ij)`) a nivel de planta, con el factor ambiental de **Nair y Allen (1993)** para baya:

```
Q            = exp(-((T - T_opt) / K_temp)^2)                 # T_opt 20,8 °C, K_temp 8,9
f_ambiental  = 1 - exp(-(Q · W / K_time)^2)                   # W = horas del periodo mojado actual, K_time 13,9 h
               (= 0 si la hora no está mojada o T > 40 °C)
p            = 1 - exp(-(β_vec·presion_vecinos + β_aire·presion_aire + β_0) · f_ambiental)
```

Chequeos del PDF que deben salir así (prueba en `tests/`): 24 h a 21 °C → 0,949; 24 h a 8 °C → 0,047. Y reproduce la tabla de arándano de UMaine: 24 h a 12 °C, 13 h a 16 °C y 10 h a 20 °C dan todos ≈ 0,34–0,40 (el umbral de riesgo alto).

- `presion_vecinos = V @ (0.5·[latente] + 1.0·[síntomas])`
- `presion_aire` solo si la ventilación de la nave está encendida.
- Latente → síntomas tras `U(latencia_min, latencia_max)` días. Síntomas → perdida si no se trata.
- `tratar(plantas)`: éxito con probabilidad `eficacia`, pasa a tratada (deja de contagiar), vuelve a sana tras `dias_proteccion`.
- Semillas de infección: 1–3 focos por temporada en plantas aleatorias (preferir `es_borde_planta`).

**Calibrar `β`** (en este orden):
1. `β_vec` con la meta del PDF: un foco, `f_ambiental = 1`, la cama contigua se infecta con ≈ **5,5 % en una semana** (`meta_cama_adyacente_7d`).
2. `β_aire` y `β_0` para que en `sensor_central` la temporada termine con **5–15 %** de plantas afectadas (supuesto).
3. Chequeo de cordura: un foco sin tratar crece aprox. como una logística con `r ≈ 0,2/día` (PDF, ejemplo [S]).

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
- `horas_mojado_24h`, `horas_mojado_72h`, `max_mojado_continuo_24h` (regla de Broome), `dias_seguidos_hr_alta`
- `dpd_min_24h` (mínimo de `T − Td`, punto de rocío), `indice_broome_24h`
- `confirmadas_misma_cama`, `confirmadas_camas_vecinas`, `distancia_a_confirmada_en_nave` (en camas; 99 si no hay)
- `ventilacion_encendida`, `es_borde`
- `edad_lectura_h` (horas desde la última medición real de esa cama; alta si solo hay sensor central)

### 3.2 Etiqueta · `prediccion/etiquetas.py`
`y = 1` si alguna planta de la cama pasa de sana a latente en los próximos 7 días (168 h). Se calcula con la verdad del simulador, solo para entrenar y evaluar.

### 3.3 Línea base: reglas biológicas · `prediccion/reglas.py`
**Índice de Broome et al. (1995)** con el periodo mojado más largo de las últimas 24 h (`W`) y su temperatura media (`T`, recortada a [12, 32]; si `T > 40` no hay infección):

```
indice        = −2,647866 − 0,374927·W + 0,061601·W·T − 0,001511·W·T²
Y             = 1 / (1 + exp(−indice))
riesgo_reglas = min(1, Y · (1 + bonus_confirmadas si hay confirmadas cerca))
```

Niveles de Broome (para el mensaje de la alerta): `≤ 0` nulo, `0–0,5` bajo, `0,5–1` moderado, `> 1` alto; se actúa desde 0,5. Chequeos del PDF: 24 h a 12 °C → 0,87; 12 h a 18 °C → 0,28.

**Importante:** la "verdad" del simulador usa Nair y Allen, y las reglas usan Broome. Son modelos distintos a propósito; si fueran el mismo, las reglas acertarían por construcción y la comparación con la IA no valdría. Limitación visible de Broome: recorta T a 12 °C, así que no ve que el frío (8 °C) frena la infección. La IA sí puede aprenderlo.

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
   - **¿Qué tan reales son los datos?** Son simulados, pero con modelos publicados: Nair y Allen (1993) para la infección, Broome et al. (1995) para las reglas y el mojado, la tabla de arándano de UMaine para validar, y un núcleo de dispersión exponencial. Los que siguen siendo supuestos (latencia en arándano, umbral de 95 % para arándano) están declarados. El siguiente paso es un piloto con un **sensor de mojado foliar** en una cama para contrastar las horas estimadas (lo recomienda el PDF).
5. **Escalabilidad (slide de negocio):** la misma estructura matemática sirve para otros cultivos cambiando solo parámetros. Ejemplo listo en el PDF: flores de corte de la Sabana, moho gris (Kerssies: riesgo si HR media > 70 % los días 6–8 antes de cosecha) y mildiú velloso de la rosa (4–21 °C, 8–12 h de mojado, el que mejor encaja con el altiplano).
6. **El ciclo fitosanitario del PDF** (prevención → monitoreo → identificación → alerta → delimitación → respuesta → evaluación) se mapea uno a uno a nuestro flujo; úsalo en la slide del flujo.

**11:30 código congelado.**

---

## Parámetros · `config/default.yaml`

Todos los parámetros viven en `config/default.yaml` (ya creado), con su fuente: `biología (Sara B.)` con la marca del PDF ([A] arándano, [P] modelo publicado en otro cultivo, [S] supuesto del reporte) o `supuesto`. No los copies aquí: el archivo manda.

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

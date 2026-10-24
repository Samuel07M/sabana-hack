# NOTAS.md · Decisiones entre Santiago y Samuel

Acordado el viernes 23 de octubre, ~22:30. Responde la Fase 0 de `planSamuel.md`. Cambiar algo aquí requiere acuerdo de los dos.

## A. Archivos compartidos
1. **`contrato/schema.sql` y `config/default.yaml`** los crea Santiago ya (hecho en este commit). El mock de Samuel los lee tal cual.
2. **`requirements.txt`** único: librerías de Santiago + `streamlit` y `plotly`. **Python 3.13** en los dos equipos.
3. **`config/default.yaml`** por secciones: Santiago es dueño de todo salvo `dashboard:`, que es de Samuel.

## B. Contrato de datos
4. **Ventilación: automática en todos los modos.** Al confirmar una incidencia en una nave con `tiene_ventilacion=1`, el simulador la apaga 48 h y escribe `ventilacion` (`motivo = 'auto: incidencia #N'`, y al reencender `'auto: fin de apagado'`) **y siempre crea la alerta `ventilacion`**. El dashboard **no escribe** `ventilacion` (solo la muestra) y `run_vivo` no la lee. *(Reemplaza las preguntas 1 y 2 de Samuel; quita los botones Apagar/Mantener.)*
5. **Alertas:** las crea el simulador. El hub solo cambia `estado` y `accion`.
6. **Acciones** (`config/default.yaml → dashboard.acciones`): tabla de Samuel. Como la ventilación es automática, la alerta `ventilacion` solo tiene `entendido`. **Ninguna acción vuelve al simulador.**
7. **`cola_sync` y modo sin red:** el simulador escribe siempre las tablas normales **y** `cola_sync` con `hora_recibida = NULL`; `tipo ∈ {lectura, inspeccion, seguimiento}`; `payload` = JSON con las columnas de la tabla destino. El botón *Pasa el celular* (hub) llena `hora_recibida`. En *Sin red* el dashboard oculta lo posterior a la última sincronización.
8. **Severidades:** `riesgo_7d` → advertencia · `confirmacion` → critica · `descartada` → info · `ventilacion` → advertencia · `seguimiento` → info, o critica si el resultado es `empeora`. Viven en `config/default.yaml → alertas.severidad`.
9. **Índices** agregados al contrato: `lecturas(corrida_id, cama_id, hora)`, `riesgo(corrida_id, dia)`, `alertas(corrida_id, hora)`.
10. **`data/finca.db`** contiene solo la corrida `demo` y una temporada `drones`. Las corridas de validación (semillas × escenarios) van a `data/experimentos/<corrida>.db`.
- Pregunta 9 de Samuel: el dashboard lee SQLite directo con `hub/db.py` (solo lectura); `hub.api` expone lo mismo en la red local.
- Pregunta 10 de Samuel: `confianza` y `plantas_afectadas` NULL en `sospecha` se muestran como "—".

## C. Entregas y demo
11. **`run_vivo` + `config/demo.yaml` a las 09:30** (no 10:30) para que Samuel ensaye. Gráficas siguen a las 10:30.
12. **03:30: `finca.db` parcial** (clima, lecturas, riesgo, alertas; sin drones) para integrar antes de las 08:00.
13. **Paso sin red en la demo:** `demo.yaml` hace que `run_vivo` escriba `cola_sync`; el guion incluye *Sin red → Pasa el celular*. Demo total ≈ 3 min.
14. **Controles de demo:** solo pausa, del lado del dashboard (deja de leer). Sin "saltar al siguiente evento".

### Horario de entregas de Santiago a Samuel
| Hora | Entrega |
|---|---|
| 23:30 | `data/finca.db` con `camas` llena y tablas vacías |
| 03:30 | `finca.db` parcial (sin drones) |
| 08:00 | `finca.db` de una temporada `drones` con todas las tablas |
| 09:30 | `python -m sim.run_vivo --config config/demo.yaml --velocidad 1` |
| 10:30 | Gráficas y `metricas.parquet` en `data/resultados/` |

## E. Decisiones de Santiago al implementar el simulador (avisar a Samuel)
16. **Contrato sin cambios.** `contrato/schema.sql` quedó igual. Valores nuevos que ve el dashboard: ninguno.
17. **`prob_ia_7d` puede ser NULL** si no existe `data/modelo_ia.joblib` (el nivel sale entonces de `riesgo_reglas`). Para la demo conviene entrenar antes: `python -m prediccion.entrenar` (≈4 min). `data/` no se versiona, así que cada quien genera su base: `python -m sim.run_temporada --escenario drones --semilla 9` (temporada con incidencias en todos los estados) y `python -m sim.run_vivo --config config/demo.yaml --velocidad 1`.
18. **`cola_sync`** se escribe en `run_vivo` y en `run_temporada` de escenarios con drones, siempre con `hora_recibida = NULL` (decisión 7). En `drones_celular` por lotes el simulador marca `hora_recibida` en la pasada diaria del celular. Las corridas de validación (`modo='experimento'`) no la escriben.
19. **Sospecha de una hora.** Una incidencia nace `sospecha` y se verifica `drones.horas_verificacion` (1 h) después → `confirmada` o `descartada`. En `run_vivo` el dashboard la verá en `sospecha` una hora simulada.
20. **Prioridad del dron: 6 h, no 24 h** (`drones.horas_sin_visita_prioridad`). Con 24 h la prioridad nunca se activaba porque la patrulla pasa por cada cama cada 7,2 h.
21. **Especificidad.** `drones.especificidad` (0,98) es la de la *verificación* de una sospecha. Las falsas detecciones por planta salen de `drones.tasa_falsa_deteccion_planta` (4e-6). Con 0,02 por planta se marcarían ~1 planta por cama visitada.
22. **Calibración (todo en `config/default.yaml` con su fuente).** `beta_vec` = 0,00294 sale de `python -m sim.calibracion` (cama contigua 5,5 % en 7 días). `beta_aire` y `beta_0` se barrieron en `sensor_central` (semillas 0-29, media ≈ 9 % de plantas afectadas). Para que hubiera suficientes horas mojadas se subieron `clima.HR_media` (82 → 88) y `clima.eventos_humedos_por_dia` (0,15 → 0,25). Un foco sin tratar crece con r ≈ 0,11-0,15/día (el plan pedía ≈ 0,2: queda por debajo, declararlo).
23. **IA.** Hiperparámetros elegidos en validación con las semillas 30-39 (del bloque de entrenamiento). Las semillas de prueba 40-49 solo se usaron para reportar. `analisis.validar` usa semillas desde 40. Hay dos modelos: `modelo_ia` (todos los datos) y `modelo_ia_central` (solo sensor fijo, escenario `sensor_central`).
24. **Corridas de validación**: no se guardan en `data/experimentos/*.db` por defecto (150 bases ≈ 2 GB). `python -m analisis.validar --guardar-db` las guarda.
25. **Demo** (`config/demo.yaml`): jornada húmeda forzada (horas 30-54, +25 % HR), foco de 3 plantas latentes en B1 · Nave 2 · Cama 14 a la hora 52, sin contagio por aire ni falsas alarmas, umbral `alto` en 0,45 (la IA es prudente sin vecinas confirmadas), 8 días = 192 h ≈ 3 min a 1 h/s.
26. **(24 oct) La base ya no se borra por defecto.** `run_temporada` y `run_vivo` conservan `data/finca.db` y solo reemplazan su propia corrida; para empezar de cero: `--recrear`. Así correr la demo no borra la temporada que usa el dashboard.
27. **(24 oct) Demo:** la jornada húmeda forzada cae solo en la **Nave 2** (antes todo el bloque → 51 alertas a la vez; ahora ≈ 13). Semilla de la demo: **35**. Las alertas `riesgo_7d` ya no se contradicen: si las reglas de Broome dicen nulo/bajo, el mensaje explica que el aviso viene del modelo.
28. **(24 oct) Escenario `actual`:** tras el tratamiento la incidencia se cierra y la cama vuelve a la ronda manual (antes quedaba `en_tratamiento` para siempre y nadie volvía a revisarla, lo que inflaba las plantas afectadas de `actual`).
29. **Pendiente, cuando Samuel suba su código:** cambiar el vocabulario de **dron → robot de riel** en todo (textos, docs y contrato: tabla `drones`, `dron_id`, fuente `'dron:B1'`).

## D. Datos biológicos (`Scientificic information.pdf`, Sara B.)
15. Parámetros del PDF pasados a `config/default.yaml`. Cambios que afectan a Samuel:
    - **Renombrado:** `clima.umbral_mojado_hr` → **`mojado.umbral_hr`**, ahora **95 %** (Broome), no 90 %. Ajustar la línea de umbral del detalle de cama (`planSamuel.md`, 2.3).
    - Clima del altiplano: T 12–18 °C (media 15), HR > 70 %.
    - Nivel de Broome (nulo / bajo / moderado / alto) disponible para el texto de las alertas `riesgo_7d`.

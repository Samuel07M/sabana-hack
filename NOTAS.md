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

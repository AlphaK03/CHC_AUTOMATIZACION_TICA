# Preparación diaria y bloqueos de lectura — 20/10/2026

El usuario observó más de 300 segundos en «Procesando día del calendario» antes
de iniciar Detalles. Se revisaron logs de los seis bots y el código compartido,
sin reiniciar la app activa ni ejecutar consultas TICA de prueba.

## Evidencia y límites del diagnóstico

En `bots/detalles/logs/workbench.log`, los nueve regímenes del 19/10 quedaron
confirmados el 20/10 a las 00:27:06. A las 00:31:30 falló `COMMIT` con
`sqlite3.OperationalError: database is locked`, dentro de `DailyJobStore.__init__`.
El calendario quedó pendiente, sin acreditar resultados que no se descargaron.
La base descargada se conserva para retomar.

El SQL anterior contaba los fallos históricos con una subconsulta por cada DUA.
Una inspección breve de solo lectura del esquema/plan de Detalles confirmó que
`attempts` no tenía índice por trabajo: SQLite indicaba `CORRELATED SCALAR
SUBQUERY` y `SCAN a`. No se ejecutó esa consulta costosa contra producción.
Esto explica una preparación que crece con trabajos del día × historial.

Los logs también contienen bloqueos de COMMIT en Talón (18/10) y BLs (19/10).
La bitácora compartida por Qt y el worker SharePoint mantenía una transacción
de lectura sin límite de ejecución. `sqlite3.connect(timeout=...)` solo limita
la espera para adquirir un bloqueo, no la duración del SELECT. Una lectura larga
puede impedir COMMIT en el modo journal existente. Se reprodujo ese mecanismo
con SQLite temporal: lector abierto, actualización del escritor y COMMIT bloqueado.
El log histórico no identifica el PID/conexión que retenía el bloqueo concreto
de Detalles; no se atribuye con certeza ese episodio a un lector específico.

También había errores Windows `WinError 5` al reemplazar `session.json` de BLs.
Ese historial es auxiliar: SQLite ya conservaba sus resultados. El reemplazo
podía coincidir con lectores breves del archivo.

## Correcciones

- `DailyJobStore` agrupa los fallos en una lectura del historial y agrega solo
  presupuestos ausentes. Conserva los existentes, incluso los rearmados por el
  usuario, las tres oportunidades y la devolución de oportunidades al cancelar.
  Sus conteos consultan los DUAs seleccionados y agrupan cantidad/intentos en
  una pasada. La reserva mantiene orden, día, exclusiones y resultados.
- Si falla la preparación, revierte la transacción y cierra la conexión creada.
  No migra esquemas, agrega índices ni cambia el modo journal.
- La consola distingue incorporación de la base al mes, preparación de pendientes
  e intentos, y verificación del día. Se aplica a los cuatro consumidores DUA.
- La lectura de bitácora tiene un presupuesto de dos segundos por conexión,
  comprobado cada 1.000 instrucciones SQLite. Al excederse, se cierra la lectura
  y la fuente queda sin verificar; no permite un cierre/subida basados en una
  verificación incompleta. Es una protección común a los seis bots, también cuando
  SharePoint verifica elegibilidad. No es un plazo para las descargas ni garantiza
  interrumpir una llamada de E/S del sistema operativo exactamente a los dos segundos.
- El conteo mensual de omitidos reúne primero los DUAs del calendario, evitando
  una subconsulta correlacionada por trabajo. Se conservan filtros por tabla,
  fecha, bot, estado y marcas manuales.
- El historial auxiliar de Manifiestos/BLs usa un temporal único y reintenta
  `os.replace` hasta cinco veces ante `PermissionError` (0,5 s de pausas en total).
  Un fallo permanente conserva el archivo anterior y sigue siendo un error.
  No cambia la confirmación SQLite, el contenido JSON ni los CSV.

## Verificación

63 pruebas pasaron con almacenamiento temporal, portales locales y Graph simulado:

```powershell
bots/detalles/.venv/Scripts/python.exe -m unittest chc_runtime.tests.test_daily_preparation chc_runtime.tests.test_daily_omissions chc_runtime.tests.test_daily_resume chc_runtime.tests.test_view_contention chc_runtime.tests.test_history_write chc_runtime.tests.test_loading_snapshot chc_runtime.tests.test_activity
workbench/.venv/Scripts/python.exe -m unittest workbench.tests.test_monthly_read_lock workbench.tests.test_monthly_progress
workbench/.venv/Scripts/python.exe -m unittest workbench.tests.test_details_daily workbench.tests.test_daily_month_retry workbench.tests.test_import_bots_bridge workbench.tests.test_transit_bridge
workbench/.venv/Scripts/python.exe -m unittest workbench.tests.test_manifiestos_bridge.ManifestIntegration.test_five_procedures_resume_and_bls_handoff workbench.tests.test_bls_knowledge.KnowledgeConnection.test_available_periods_pipeline_and_resume chc_cloud.tests.test_service
```

La comparación diaria usa 12.000 trabajos, 24.000 intentos y una selección de
2.000 DUAs. El cálculo anterior tardó **5,461 s** y la apertura/preparación nueva
**0,038 s** en esa prueba. Presupuestos, resumen y hashes CSV/TXT/JSON idénticos;
trabajos, intentos y resultados sin cambios. No son tiempos garantizados para
bases reales. La prueba de bloqueo confirma que el lector acotado libera al
escritor; la del historial cubre bloqueo transitorio y fallo permanente.

También se comparó el lector mensual anterior (`2c5e80f`) y el nuevo sobre los
mismos 10.000 DUAs/20 días sintéticos: toda la bitácora idéntica y hashes SQLite
intactos. Ambos tardaron aproximadamente 0,05 s en esa muestra; no se atribuye
una mejora porcentual de carga a ese caso.

La instancia abierta se conservó antes de documentar. Las correcciones requieren
el siguiente arranque voluntario; no se reemplazaron procesos ni datos activos.

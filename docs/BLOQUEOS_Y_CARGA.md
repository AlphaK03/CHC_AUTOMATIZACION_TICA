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

## Revisión posterior: Manifiestos permanece cargando (20/10)

El usuario cerró la app tras informar que Conocimientos y DUAs tardaban minutos.
Se verificó que no hubiera app ni workers abiertos. Se copiaron las cuatro bases
activas (aproximadamente 443 MB en total) y las sesiones a
`runtime/diagnostics/batch-loading/copy`, con rutas y salida aisladas.
No se iniciaron consultas TICA, reexportaciones ni cargas a SharePoint.

La espera de minutos **no se reprodujo**. El primer arranque frío del proceso
de Conocimientos tardó 10,6 s; su refresh, unos 0,03 s. DUAs abrió en 1,0 s,
con lectura de unos 0,08 s. En el recorrido QML completo, con seis módulos
iniciando a la vez, Conocimientos estuvo listo en 1,44 s; DUAs, aproximadamente
1,8 s después de seleccionar su procedimiento. Estos tiempos corresponden
a este equipo y estas copias; no garantizan un plazo para otros volúmenes.

Se confirmó un defecto distinto de SQLite: `BatchBridge.loading` también
dependía del generador de bases/catálogo auxiliar. Podía ocultar la sección lista
o su error mientras el auxiliar siguiera ocupado. Ahora depende solo del
procedimiento seleccionado; el diálogo/selector auxiliar conserva sus indicadores.
No se dispone de una traza del incidente original para afirmar que este defecto
explique por sí solo toda la espera reportada.

Como protección, Qt supervisa durante 60 s exclusivamente `refresh`, `select`
y `knowledge_catalog`, incluida su inicialización. Si vencen, cierra ese proceso,
conserva los datos confirmados, descarta respuestas tardías y muestra el error
con **Más → Reconectar**. `select` solo guarda la selección del catálogo mediante
reemplazo atómico después de leer; no confirma resultados. No se aplica ese plazo
a descargas, exportaciones, importación o generación de bases. Los procedimientos
hermanos siguen funcionando. No cambia el timeout HTTP ilimitado de DUAs.

El indicador muestra etapa, segundos y señal del proceso. El log persistente
registra comienzo/fin/duración de cada lectura local; los estados y conteos
SQLite tienen etapas separadas. Los parsers, SQL de conteo, resultados y formatos
no cambiaron. Se compararon antes/después:

- Conocimientos: 2.292 manifiestos guardados, 446.522 filas.
- DUAs: 2.282 guardados de 2.292, 10 excluidos y 1.595.374 filas.
- Resúmenes por modalidad, 200 trabajos visibles y hashes SQLite idénticos.
  También se verificaron los hashes de los originales.

Pasaron 11 pruebas:

```powershell
workbench/.venv/Scripts/python.exe -m unittest discover -s workbench/tests -p test_batch_loading_timeout.py -v
workbench/.venv/Scripts/python.exe -m unittest discover -s workbench/tests -p test_loading_*.py -v
workbench/.venv/Scripts/python.exe -m unittest discover -s workbench/tests -p test_manifest_modes*.py -v
workbench/.venv/Scripts/python.exe workbench/app.py --smoke-test
```

Además, el recorrido QML con las copias abrió los seis módulos y los cinco
procedimientos, conservó la navegación y terminó sin avisos QML. El diagnóstico
local `runtime/diagnostics/batch-loading/` conserva scripts, capturas, snapshots
y hashes; no se versionan datos del usuario. La prueba de lector sin respuesta
verifica cierre, mensaje, conservación de datos y reconexión a un worker real;
la de comandos protegidos comprueba que nunca se detienen escritores/descargas.

Se abrió la app actualizada en Vista general antes de documentar, sin iniciar
descargas. Su log confirmó la carga local de Conocimientos en 0,063 s.

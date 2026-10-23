# Contexto de CHC Workbench para una nueva sesión

## Estado vigente — 22 de octubre de 2026

- Limpieza de evidencias XMovimientos completada por instrucción expresa del
  usuario: eliminados únicamente 31.242 HTML/JSON de
  `%LOCALAPPDATA%/CHC Consultores/Workbench/bots/xmovimientos/data/exports/daily-2026-10/diagnosticos`.
  Total retirado: 10.753.741.896 bytes (10,75 GB); carpeta sin archivos, cero
  errores. Se tomaron los bloqueos de cola del motor y se verificaron iguales
  los SHA-256 de SQLite/CSV antes y después. No se consultó TICA, reabrieron
  trabajos ni borraron resultados/calendarios. Otras copias y respaldos intactos.
  Recibo en `runtime/diagnostics/movement-evidence/deleted-20261023T003540.json`
  (fecha UTC). La falta del HTML no reconsulta DUAs confirmados ni reconstruye
  evidencia: Abrir evidencia de esos históricos ya no encontrará el archivo.
  Las futuras consultas que lo requieran usarán el resumen acotado ya instalado.

- XMovimientos: 11,84 GB de HTML de diagnóstico frente a 36,9 MB de SQLite mensual
  en los datos instalados de C. Guardaba páginas completas para Vacío, incluidas
  tablas de manifiestos ajenas a movimientos. Ahora `movement_evidence.py`
  conserva fichas HTML verificables de hasta 32 KiB, con identidad/fecha,
  encabezados/conteos/errores/paginación, tres filas de muestra y firma/tamaño
  originales. El lector acepta resúmenes y HTML antiguos; formatos corruptos o
  incompletos nunca confirman Vacío. No cambia parsers copiados, resultados,
  calendario ni los diagnósticos de los otros bots.
  `tools/compact_movement_evidence.py` y `Resumir_Evidencias_XMovimientos.bat`
  convierten históricos tras `BORRAR` exacto; revisión por defecto sin cambios,
  bloqueos compatibles, reemplazo atómico, rutas/fechas conservadas, diario con
  hashes y operación repetible. No abre SQLite ni elimina CSV.
  Históricos conservados en la entrega inicial: conversiones probadas en almacenamiento temporal y
  ejemplos existentes solo en lectura. Mayor HTML: 14.145.681 → 1.746 bytes con
  la misma comprobación de vacío. Pasaron 13 pruebas evidencia/vacíos, 21 de
  puentes/bitácora y smoke de seis vistas. Ver `INTEGRACION_IMPORTACION.md`.
  Antes de documentar se abrió la app del repositorio usando datos C mediante
  `CHC_WORKBENCH_HOME`, sin consultas. No había instancia previa.
  Actualización posterior: el usuario descartó convertir históricos por tiempo
  y energía y considera volver a descargar. Se recomendó retirar solo diagnósticos
  conservando resultados; después autorizó la limpieza indicada arriba, sin conversión masiva.
  La instalación C ya incorpora los cuatro archivos de runtime de `e45654d`
  (40.463 bytes), con respaldo previo, metadatos y hashes instalados actualizados.
  Evidencia/respaldo en `runtime/diagnostics/movement-evidence/install-update/20261023T002359/`.
  Verificado con Python instalado y almacenamiento temporal: respuesta sintética
  de 2.000.268 bytes → 1.779 bytes, Vacío durable al reabrir, sin red; smoke del
  EXE correcto. App instalada abierta antes de documentar, sin consultas.
  El acceso directo habitual carga la corrección; el instalador anterior en
  `runtime/releases/` aún conserva el payload previo (no se reempaquetó).

- Migración de datos a la instalación C autorizada después por el usuario para
  probar la carga. Instalada en `%LOCALAPPDATA%/Programs/CHC Workbench/20261022-002420-76a546`;
  datos en `%LOCALAPPDATA%/CHC Consultores/Workbench`. Se cerró normalmente la
  instancia D sin consultas activas. Copiados 35.542 archivos, 13.487.958.875 bytes,
  incluidos diagnósticos, resultados, calendarios, configuraciones y SharePoint
  del mismo usuario. Hashes originales intactos; SQLite de bots idénticos byte a
  byte antes de abrir, 54 quick_check correctos. Ajustadas 46 entradas de metadatos
  JSON/rutas de registros de publicación, conservando firmas y resultados.
  Respaldo de los datos previos de C: carpeta hermana
  `Workbench.antes-migracion-20261022-003401`. D permanece completo e independiente.
  Prueba con intérprete instalado: seis bots listos en 11,4–14,3 s; todos los
  procedimientos de Manifiestos cargan sin errores. Bitácora D/C idéntica: 60,203 s
  frente a 1,766 s en esta lectura. Para leer D se amplió a 60 s únicamente el
  plazo del diagnóstico; la app conserva 2 s. Sin descargas TICA ni subidas de prueba.
  App instalada abierta al terminar, procesos con almacenamiento C comprobado.
  Evidencia en `runtime/diagnostics/migration/20261022-003401/` y scripts puntuales
  en `runtime/migrate_installed_data.py`, `verify_migrated_load.py` y
  `compare_migrated_progress.py`. Quedó una copia temporal incompleta
  `Workbench.migracion-20261022-003022`: revisión automática bloqueó su limpieza;
  no es almacenamiento activo. No confundirla con el respaldo previo de C.

- Distribución Windows x64 en `distribution/windows/`: lanzador e instalador C#,
  Python privado por motor, paquetes comunes deduplicados y un Chromium para
  Playwright/Selenium. Sin datos, sesiones ni rutas del equipo en el paquete.
  `chc_runtime/distribution.py` separa código y datos por usuario; desarrollo
  conserva sus rutas. `selenium_browser.py` adapta solo el navegador del proveedor.
  Ver `DISTRIBUCION_WINDOWS.md` para comandos, limitaciones y verificaciones.
  Carpeta QA trasladada con espacios/acento: puentes Qt y BLs verificados offline.
  App empaquetada abierta con almacenamiento vacío propio antes de documentar;
  no se interrumpieron consultas ni se migraron bases actuales. Queda pendiente
  aceptación en otro equipo físico limpio. Instalador y mediciones finales en
  `runtime/releases/`; evidencia en `runtime/diagnostics/distribution/`.
  Recomendación solicitada: código/entornos/SQLite activos en C SSD y respaldos
  en D HDD. El repositorio sigue en D; posteriormente se migraron los datos a
  la instalación C, según la nota anterior.

- Revisión posterior **sobre el entorno real**, solicitada expresamente: logs
  07:10–07:11 confirman COMMIT bloqueado en Detalles/Talón y claim de XMovimientos.
  Se inspeccionó con py-spy la instancia 30412 y sus workers; Tránsito está en
  automático esperando la siguiente fecha, se conserva abierto. No reiniciar
  esta instancia sin autorización: los otros tres motores terminaron por error.
  BLs reprodujo en sus SQLite originales una lectura >30 s: primero conteo de
  resultados, después agregación de TODOS los checkpoints para mostrar 200 jobs.
  Disco D: HDD, muestra de cola 4 y ~1,18 MB/s; no se identificó retrospectivamente
  el PID lector exacto que causó cada COMMIT fallido. No atribuirlo a duplicación
  de workers: los pares de PID son launcher venv + intérprete.
  Correcciones: inspect BLs obtiene la página visible primero, agrega checkpoints
  por claves exactas vigentes de esos jobs, preservando los filtros originales.
  `sqlite_read.prepare_reader` aplica query_only/mmap 256 MiB por conexión, sin
  cambiar archivo/journal; plazo comprobado cada 10 instrucciones (antes 1000).
  Bitácora conserva 2 s; summary/lista DUA tienen 10 s; view interrumpida durante
  descarga se difiere igual que SQLITE_BUSY. No cambian parsers ni motor escritor.
  Validación real: worker BLs refresh 0,156 s; comparación antigua/nueva en caliente
  0,422/0,172 s, snapshot idéntico en cuatro vistas (inicio, final, búsqueda, vacía),
  hashes de todos sus SQLite intactos. Bitácora real de seis módulos idéntica,
  cero errores, 1,500/1,235 s. Lecturas DUA 0,016–0,110 s y BEGIN EXCLUSIVE/ROLLBACK
  inmediato sin DML/DDL en los tres archivos; no consultas TICA de prueba.
  Evidencia local en `runtime/diagnostics/live-locks/`, detalles y límites en
  `docs/BLOQUEOS_Y_CARGA.md`. Cambios requieren cargar de nuevo los procesos;
  la instancia existente conserva código anterior y automático de Tránsito.

- Incidente posterior: Conocimientos/DUAs permanecían en «Cargando». Con la app
  cerrada se copiaron sus cuatro SQLite y sesiones a almacenamiento de diagnóstico,
  reescribiendo rutas; pruebas sin consultas TICA. No se reprodujo la espera de
  minutos: refresh SQLite 0,03–0,08 s, primer proceso frío 10,6 s. En QML con
  seis módulos concurrentes Conocimientos listo en 1,44 s y DUAs aproximadamente
  1,8 s desde seleccionar; resúmenes, modalidades, trabajos visibles y hashes
  antes/después idénticos (446.522 y 1.595.374 filas respectivamente).
  Se corrigió un defecto comprobado de `BatchBridge.loading`: un auxiliar ocupado
  ocultaba un procedimiento ya listo o su error. El auxiliar conserva sus propios
  indicadores. Cargas locales refresh/select/knowledge_catalog tienen supervisor
  Qt de 60 s; termina solo ese lector, descarta mensajes tardíos y permite
  reconectar. Nunca aplicar a run/export/import/base_build/knowledge_build.
  SectionLoading muestra etapas/señales y batch_worker registra inicio/fin y
  duración de lecturas; inspect distingue estados y conteo de resultados.
  11 pruebas pasaron, más smoke y recorrido QML de seis módulos/cinco procedimientos
  con las copias, sin avisos. App actualizada abierta en Vista general antes
  de documentar; carga real de Conocimientos registrada en 0,063 s. No atribuir
  la demora histórica exclusivamente al defecto visual: no hubo traza del bloqueo.
  Evidencia y límites en `docs/BLOQUEOS_Y_CARGA.md`.

- Revisada la espera larga de Detalles tras regímenes: log 20/10 00:27:06 base
  completa; 00:31:30 `database is locked` al confirmar preparación diaria.
  El plan de solo lectura mostró conteo correlacionado del historial sin índice.
  `DailyJobStore` ahora agrupa los intentos una sola vez, conserva presupuestos
  existentes y consulta la selección diaria para resúmenes/reservas. Cierra su
  conexión al fallar la preparación. Sin migración ni cambios de journal/formato.
  Consola distingue incorporación, preparación de pendientes y verificación.
  Bitácora compartida Qt/SharePoint: lectura limitada a 2 s por conexión mediante
  progress handler; una consulta interrumpida queda sin verificar, nunca completa.
  Conteo de omitidos sin subconsulta correlacionada. Reproducción aislada de lector
  que impide COMMIT; el log no identifica al lector exacto del incidente histórico.
  Se observaron también bloqueos en Talón/BLs y reemplazos JSON con WinError 5:
  historial Batch con temporal único y hasta cinco intentos breves de reemplazo.
  63 pruebas offline pasaron; preparación sintética anterior/nueva 5,461/0,038 s,
  con presupuestos, resumen y exportaciones idénticos. Bitácora antes/después
  idéntica sobre 10.000 DUAs/20 días; hashes SQLite intactos. Evidencia, comandos y
  límites en `docs/BLOQUEOS_Y_CARGA.md`. App activa conservada antes de documentar;
  cambios al próximo arranque voluntario, sin consultas reales de prueba.

- Arranque y carga independientes por petición del usuario: el inicio normal
  abre siempre Vista general, incluso si un acceso antiguo pasa `--page`.
  Capturas, smoke y demo conservan la elección de vista. `app.py` crea QML antes
  de encolar las conexiones; cada bot carga en su QProcess y la bitácora conserva
  su lector en un hilo. No se esperan todos los motores para poder navegar.
  `SectionLoading.qml` sustituye el bloqueo global anterior: animación local en
  Detalles/Tránsito/Talón/XMovimientos y BLs/Manifiestos. Conserva la navegación
  entre procedimientos y la ruta/pestaña al terminar cualquier carga. Las tarjetas
  distinguen Cargando de Consultando. Error/cierre/descargas conservan sus controles.
  `DetailsService.snapshot` reutiliza el resumen activo calculado en la misma
  petición: no cambia SQL ni mantiene caché entre peticiones. Batch `connectModule`
  es idempotente al navegar; `refreshModule` conserva la recarga explícita de
  Más → Reconectar y `refreshKnowledge` sigue atendiendo cambios del productor,
  incluso si llegan durante otra lectura. La preparación de BLs y sus firmas
  no cambian. No se modificaron los motores copiados ni datos originales.
  Comparación offline en `chc_runtime/tests/test_loading_snapshot.py`: dos SQLite
  sintéticos de 18.000 trabajos cada uno, seis estados, revisiones y retenidos;
  lectura anterior y nueva sobre los mismos archivos en los cuatro perfiles.
  Resúmenes/tablas idénticos, hashes intactos y escrituras nuevas visibles en la
  siguiente petición. Con dos tablas pasa de tres lecturas a dos; medición local
  anterior/nueva en segundos: Detalles 0,0278/0,0223; Tránsito 0,0283/0,0215;
  Talón 0,0265/0,0194; XMovimientos 0,0339/0,0250. No es una medición del arranque
  con bases de producción ni una garantía de tiempos en otro equipo.
  Validación: comparación con el Python de Detalles; 1 prueba de conexiones Qt
  con proveedor real y fuentes temporales; 5 de carga/QML Manifiestos/Detalles;
  2 de integración offline (cinco procedimientos, BLs y reanudación); 3 de
  actividad/filas activas; smoke de las seis vistas. Capturas claro/oscuro en
  `runtime/diagnostics/loading-independent/`, sin avisos QML. La app estaba cerrada:
  se abrió la versión actualizada antes de documentar, sin iniciar consultas.

- Actividad convertida en consola común para los seis bots y cinco procedimientos
  de Manifiestos. `chc_runtime/activity.py` observa etapas con contextvars, pilas
  por tarea/hilo y un hilo de señal cada segundo (también durante exportaciones
  síncronas); cada 15 s registra la etapa que sigue esperando. No impone plazos,
  consulta bases ni confirma resultados. El cierre del supervisor retira también
  etapas de tareas abandonadas para no mostrarlas como consultas vigentes.
  `worker.py` y `batch_worker.py` envuelven inicialización/comandos de primer
  plano; las lecturas Qt concurrentes no reinician el monitor. Batch transmite
  también logging original por JSONL y conserva sus logs persistentes.
  `manifest_activity.py` instrumenta métodos y funciones en memoria, sin editar
  fuentes copiadas: HTTP, parser, formulario, modalidad y exportación. DUAs sigue
  con timeout HTTP 0, un intento y sin recuperación de errores dentro de la misma
  consulta. Los cuatro DUA observan formulario/CAPTCHA/respuesta, páginas, pausas,
  diagnósticos y CSV; BLs búsqueda/identidad/HTTP/páginas/checkpoints. Diario muestra
  proveedor base, día y espera de 00:01. Sin cambios de calendarios/colas/datos.
  Qt usa `live_activity.py`, `ActivityConsole.qml` y `ActivityView.qml` incremental:
  etapas, segundos, última señal real, ampliación y limpieza visual. El reloj
  no acredita avance de TICA. Tras 10 s sin mensajes advierte falta de señales.
  Historial y etapas conservan el desplazamiento manual; modelos no se resetean
  en cada tick. Pruebas y límites en `docs/ACTIVIDAD_CONSOLA.md`. Capturas sintéticas
  aisladas en `runtime/workbench/captures/activity-console/`. App abierta conservada
  antes de documentar; cargar la nueva interfaz al próximo arranque voluntario.

- SharePoint rediseñado y acceso a cuenta en el avatar superior: navegación se
  llama solo SharePoint; diálogo Resultados/Archivos/Actividad, destino + local,
  selección mensual, exploración de archivos con tamaño/fecha y apertura, creación
  explícita de subcarpetas y búsqueda/filtros de últimos 50 envíos. Totales de
  toda la cola aparte. Conservar navegación desde funciones del diálogo, no desde
  contextos de delegados destruidos; búsqueda reinicia sitio/biblioteca elegidos.
  `AccountAvatar.qml` dibuja foto circular local o iniciales. Menú con nombre,
  correo, conexión/cambio, actualizar perfil, desconectar y SharePoint.
  Se revisó el registro OAuth2 par CHC REPORTES en Edge: mismo appId, 17 permisos
  configurados y User.Read delegado concedido para CHC. El usuario autorizó usar
  los necesarios: se añadió User.Read a `sharepoint_app.json`, sin cambiar Entra,
  sumar correo/Power BI, secretos o .default. Actualizada la restricción de AGENTS.
  `chc_cloud/profile.py` guarda nombre/foto opcionales ligados a hash de cuenta;
  desconectar limpia, otro usuario nunca hereda foto. Errores no bloquean archivos.
  Auth separa adquisición User.Read de Files/Sites para no romper sesiones previas;
  reconectar por acción del usuario si falta perfil. JPEG/PNG ≤4 MiB, 404 sin foto,
  sin redirecciones ni tokens en Qt. API nueva destination_contents valida cuenta;
  create_folder valida padre consultado/nombre y usa fail en conflictos. No cambia
  destino ni inicia envíos. Se conservan SQLite, CSV, eTag y propiedad de subidas.
  Pasaron 31 pruebas offline + smoke seis vistas; capturas sintéticas en
  `runtime/diagnostics/sharepoint-ui/`, oscuro 1280×820 y claro 1000×600 sin avisos.
  Sin consultas de perfil/escrituras cloud reales como prueba. App activa conservada
  antes de documentar; la interfaz se carga al próximo arranque.

- Progreso visual común en los seis bots y cinco procedimientos de Manifiestos:
  `workbench/qml/components/ProgressSummary.qml` presenta cantidad/total destacados,
  porcentaje, estado y barra con segmentos verde (confirmados), naranja (en curso),
  dorado (por revisar) y gris (excluidos), más contadores alineados que ajustan
  filas. El fondo conserva el trabajo sin confirmar. `DetallesPage.qml` lo usa
  para los cuatro DUA; mantiene Reintentar mes, estado y tiempo restante.
  `ManifiestosPage.qml` agrupa total y modalidades dentro de una sola sección,
  con dos columnas desde 640 px interiores y una en anchos menores; actividad,
  búsqueda, filtro e historial siguen disponibles debajo. Sin tarjetas por cifra.
  Theme incorpora warning en ambos temas. Las modalidades sin actividad muestran
  En espera si el bot está ocupado; no cambia planificación ni hilos.
  Porcentaje = confirmados/total; vacíos DUA se agregan como antes, vacíos BLs
  ya incluidos en Guardado y excluidos separados. No cambiar fuentes, estados,
  datos ni reglas del backend por esta presentación. Cambio solo QML.
  Pasaron 5 pruebas QML enfocadas y smoke visual aislado de las seis páginas y
  cinco procedimientos, oscuro a 1280×820 y claro a 1000×600, sin avisos QML.
  Doce capturas y report.json en `runtime/diagnostics/progress/`; script local
  `runtime/diagnostics/preview_progress.py`, sin workers ni consultas.
  Al finalizar la app estaba cerrada: se abrió actualizada en BLs antes de
  documentar. No se interrumpió la revisión Edge existente ni se iniciaron consultas.

- BLs muestra resúmenes independientes por modalidad: guardados/total y estado
  Completado/Descargando/Con pendientes, más pendientes, en curso, inválidos,
  filas confirmadas y vacíos. `bls_observation.py` deriva el modo del IDManifiesto
  (también archivos externos/antiguos), lee todos los trabajos en ready/finished
  y actualiza deltas en memoria por evento, sin SQL por página. No sumar páginas
  parciales como confirmadas ni depender de las 200 filas/búsqueda. Repeticiones
  de página no inflan conteos. `manifest_service.py` recupera en solo lectura y
  transmite `modeSummaries` por el puente existente; reservas huérfanas se muestran
  pendientes al detener. QML conserva el resumen global y añade dos resúmenes
  de modo, con modalidad también en Descargando ahora. No cambia colas, firmas,
  datos ni exportaciones. Completado de modo describe el lote, no prueba cobertura
  mensual. 11 pruebas offline enfocadas pasaron; captura compacta aislada en
  `runtime/diagnostics/bls-modes.png`, QML sin avisos a 1280×820 y 1000×600.
  Al terminar la instancia anterior ya estaba cerrada; se abrió la app actualizada
  en BLs antes de documentar, sin iniciar consultas ni detener la revisión Edge.

- BLs acumula desde Conocimientos dentro de la **misma selección exacta de meses
  y modalidades** y configuración de búsqueda. Pasar de 250 a 251 conserva el
  lote/SQLite/CSV existentes: añade solo nuevos, consulta pendientes presentes
  en la instantánea actual y omite Guardado, incluidos vacíos. Una selección menor
  o vacía conserva resultados; otro mes/modo queda separado. No fusionar lotes
  históricos duplicados: elegir activo compatible o mayor avance.
  `chc_runtime/bls_incremental.py` fija la firma/ruta originales del motor y sus
  páginas, conserva ordinales, payloads, intentos y generaciones de reconsulta.
  Valida mes/modalidad e identidad manifiesto/secuencia/BL contra lo persistido;
  contradicciones detienen la ampliación. Adopción de lote antiguo con respaldo
  en `data/backups/bls_incremental/`, fuera de jobs; inserción transaccional,
  prueba hash de entrada acumulada y solicitudes/miembros auditados en SQLite.
  `bls_session.py` conecta el adaptador bajo la reserva original;
  `manifest_service.py` conserva identidad/publicSpecs y reconsulta explícita
  de vacíos. El alcance de cola compartido con `bls_empty_retry.py` mantiene
  todas las rondas dentro de la solicitud. Las fuentes copiadas siguen intactas.
  Pasaron 35 pruebas offline (24 runtime y 11 puente/proveedor/QML), incluidas
  adopción antigua, crecimiento/reordenación, separación de mes/modo, menor/vacía,
  conflicto, rollback, respaldo fallido y paginación/reconsulta tras ampliar.
  App activa conservada antes de documentar, sin consultas reales ni cambios
  de bases del usuario. La mejora se carga al próximo arranque.

- La espera global anterior fue sustituida por carga local de cada sección
  (véase el primer punto). Se conservan los estados `loading` de los puentes:
  inicialización/lectura/selección/importación y acuse idle después de ready/result.
  Demostración, errores, cierre, run/retry_empty/diario y las lecturas de progreso
  durante descargas no activan la espera. Tampoco la preparación para iniciar BLs.

- Identidad visual CHC actualizada desde las opciones proporcionadas en
  `SYS_CARGA_TRANSITO/Logos_CHC`. Copias propias en `workbench/assets/branding`:
  símbolo SVG de `CHC_vectorizados.zip` e ICO `Logo_CHC_REPORTES.ico` con seis
  tamaños (16–256 px). `components/BrandMark.qml` presenta el símbolo sobre blanco
  en la barra lateral (expandida/contraída) y Acerca de; colores originales.
  `app.py` configura `QGuiApplication.setWindowIcon` y el AppUserModelID de Windows
  `CHC.Consultores.Workbench`, sin cambiar instancia única, motores o datos.
  Los recursos externos permanecen intactos y no son una dependencia de ejecución.
  Smoke de las seis vistas y tres capturas aisladas (oscuro, claro/contraído y
  Acerca de a 1000×600) pasaron sin avisos QML; ICO comprobado en todos sus tamaños.
  Capturas en `runtime/diagnostics/branding`. Se conservó la app activa, sin
  reiniciarla; logo/icono se cargan completamente al siguiente arranque.

- BLs incorpora **Más → Reconsultar BLs con 0 filas…**, con conteo/confirmación
  para el lote activo y resumen de guardados sin líneas. Comando `retry_empty`
  independiente del proveedor: reconstruir la entrada desde `inputs`, comprobar
  firma/ruta/configuración original y no crear otra identidad ni leer de nuevo el
  archivo de entrada. `bls_empty_retry.py` respalda SQLite fuera de `data/jobs`,
  conserva intentos y registra solicitud/miembros; reabre solo Guardado con
  `result_count=0` y cero resultados reales. Cola acotada a esos miembros en
  todas las rondas; preservar los pendientes anteriores y los BLs con líneas.
  Se mantiene el bloqueo original y se rechazan selección cambiada/lote ocupado.
  Cada reconsulta inicia un avance por páginas nuevo mediante generación
  persistida por job; las páginas anteriores permanecen intactas. `PageStore`
  y la observación de página/filas resuelven únicamente la generación vigente.
  Ante fallo/detención, los reabiertos quedan pendientes y el inicio normal
  recupera ese avance nuevo; ese inicio normal conserva su alcance habitual.
  El guardado original actualiza filas y CSV acumulado sin duplicar resultados.
  Sin consultas/subidas automáticas ni cambios en fuentes copiadas. 23 pruebas
  locales pasaron (14 páginas/portal, 2 cola/respaldo y 7 puente/QML/recuperación),
  incluida conversión vacío→con líneas, repetición vacía, reanudación, alcance de
  rondas, entrada externa ausente y bloqueos. Captura compacta en
  `runtime/diagnostics/bls-empty-retry.png`. La app se encontró cerrada y se abrió
  la versión actualizada en BLs antes de documentar, sin iniciar consultas reales.

- BLs acepta números de manifiesto con una letra ASCII final (`2601287L`),
  además de los numéricos. La consulta manual solicitada confirmó en TICA
  `4-1-2601287L-P001-13/10/26`, con 22 conocimientos (20 Courier N y 2 S).
  El rechazo anterior provenía del generador y de `core.inputs`, ambos numéricos.
  `chc_runtime/bls_identifiers.py` adapta sus validaciones solo en los procesos
  correspondientes, sin modificar fuentes copiadas. Una copia numérica se usa
  exclusivamente para validar el resto de los campos y ordenar la exportación;
  consultas, filas, auditoría, claves y payloads conservan el texto original.
  Se habilita en proveedor, generador manual y entrada BLs (SQLite/XLSX).
  Números anteriores mantienen claves/firmas; letras distintas no se fusionan.
  No aceptar otros patrones desconocidos ni saltar Courier N, conflictos,
  fechas, secuencia, identidad, checkpoints o reservas. No migrar trabajos
  antiguos ni reconstruir éxitos desde la auditoría de una preparación rechazada.
  26 pruebas offline pasaron: generador automático/manual, ceros, firmas,
  conflictos y formatos rechazados, portal local con paginación/reanudación,
  BLs–Conocimientos/QML y repetición sin reconsultar Guardado. Datos temporales,
  sin consultas TICA nuevas como pruebas. App activa conservada; cambio completo
  al próximo arranque (Reconectar solo refresca, no recarga procesos).

- Corrección de bitácora para DUAs por manifiesto: reconocer el estado real
  `Finalizada con exclusiones`, además de `Finalizada`. Las exclusiones por
  frmAmbiente cuentan como omitidas fuera del CSV y permiten Al día/Completado
  solo con cobertura verificada de cada modalidad, selección terminada y ausencia
  de parciales en los trabajos guardados. Antes Aéreo podía mostrar Pendiente
  pese a tener cobertura y cero pendientes. El reintento normal sigue saltando
  Excluido; no hay control para reabrir esas exclusiones. Más → Pendientes y
  exclusiones permite revisar el motivo. Sin cambios en motores ni datos reales.
  21 pruebas offline de bitácora/QML pasaron, con diez exclusiones, ambas
  modalidades, cobertura acumulativa/antigua y lectura sin escrituras. La app
  abierta se conservó; el cambio se carga al próximo arranque.

- Seis módulos operativos: Detalles, DUAs Tránsito, Talón, XMovimientos, BLs y
  Manifiestos; este último tiene cinco procedimientos y genera bases para BLs.
  Motores separados, SQLite/progreso conservados, actividad estable y revisión
  visible en TICA sin cambiar el estado de una descarga.
- Ajuste visual global, 17/10: la captura real confirmó 250 filas Marítimo,
  1833 Aéreo y 2083 totales; la tabla de 90 px dejaba oculta una de las dos filas.
  Manifiestos/BLs reservan altura para 2–5 filas, con filas de 42/66 px para
  acomodar TICA. DUA adapta la altura de listas cortas. Cabecera/márgenes compactos,
  navegación lateral desplazable y procedimientos en dos filas al reducir ancho.
  Barras visibles cuando se necesita desplazar. `components/AppDialog.qml` centra
  ventanas en Overlay, comparte tema y Cerrar; calendario con contenido desplazable
  y pie fijo. Se conservaron las funciones, fuentes, motores y almacenamiento.
  Pruebas: 13 tests locales pasaron; `test_platform_layout.py` genera 229 capturas
  de páginas/diálogos, tres tamaños (1280×774, 1000×680, 1000×600), temas y demo,
  sin controles fuera del ancho, verificando ambas filas y sus botones completos,
  acceso al final del contenido y cierre real de diálogos. Capturas en
  `runtime/diagnostics/layout/` al fijar `CHC_LAYOUT_CAPTURES`; fixture solo memoria/
  temporales, sin red ni motores. La app inicial se conservó mientras estuvo abierta;
  al comprobar que ya estaba cerrada se abrió la versión ajustada sin iniciar consultas.
- Observación de Manifiestos por modalidad: columna y resumen para Marítimo,
  Aéreo y Terrestre, filtro del historial y paginación conjunta sin perder filas.
  La clave interna de observación es `(base SQLite, jobId)`; no usar solo el ID:
  dos bases tienen `listado` y antes una ocultaba a la otra en la GUI. SQLite y
  CSV estaban separados y conservan sus datos. `BatchService` agrega resúmenes
  por base/modalidad, tanto en progreso como al inspeccionar históricos; callbacks
  capturan modalidad/ruta por iteración. Activos visibles antes del límite de 200
  e independientes del filtro. TICA recibe la base elegida y `manual_review_data`
  comprueba pertenencia al lote antes de leer en modo solo lectura. Fuentes
  originales intactas; no hay migración ni descargas nuevas al abrir esta vista.
  Diez pruebas offline pasaron, incluidos los cinco procedimientos con ambas
  modalidades, reintentos, carga posterior, paginación, conteos y QML/TICA.
  La instancia activa se conservó; cambio completo al próximo arranque.
- Borrado seguro disponible en los seis bots. Los cuatro DUA exigen **BORRAR**
  para quitar filas, limpiar completados o eliminar tabla, validado por el worker.
  Manifiestos (sus cinco procedimientos) y BLs añaden **Más → Eliminar base de
  datos…** sobre la ejecución elegida, también con **BORRAR** exacto. Conservar
  bases de entrada y CSV públicos; archivar solo el trabajo interno propio en
  `data/deleted/<flow>/<operación>/`, fuera de las fuentes/bitácora. Validar ID,
  nombre, procedimiento, ruta y bloqueos del motor. Traslado reversible con
  diario y recibo `deletedBatches` en session.json: revertir cierres antes del
  commit sin resucitar borrados confirmados al recrear el mismo ID. Recuperación
  de un borrado confirmado manual, sin botón Restaurar. La app activa se conserva;
  estos cambios se cargan al próximo arranque.
  Validación: 20 pruebas offline (8 de borrado/recuperación, 9 de integración
  Manifiestos/BLs/Detalles/QML y 3 de Tránsito/Talón/XMovimientos). Las pruebas
  antiguas de rango diario ahora envían `bounded=True`; el modo normal conserva
  su ejecución continua. No se borraron bases reales ni se consultó TICA.
- Manifiestos acumula los cinco procedimientos por mes/Courier sin IDs/límite.
  Repetir, ampliar fechas o cambiar modalidades reutiliza la ejecución y agrega
  manifiestos nuevos, conservando Guardado/intentos/checkpoints. Los CSV siguen
  separados por modalidad. Cobertura exacta en `workbench_queries` y miembros
  firmados; bitácora y proveedor BLs no deducen el mes desde el último intervalo.
  Migraciones con respaldo en `data/backups/`, fuentes copiadas intactas. No se
  fusionan bases históricas ni se cambian firmas/checkpoints del motor BLs.
- Vista general: cada bot de la bitácora muestra el conteo **16/31**, solo números,
  blanco y negrita a 22 px, junto al nombre. Incluye aceptación manual; en
  Manifiestos cuenta fechas comunes a los cinco procedimientos y sus modalidades.
  El tema claro añade fondo oscuro al número para conservar el contraste.
- Calendario de los cuatro DUA: **Marcar completado** / **Quitar marca manual**
  permite poner un día en verde bajo criterio del usuario, incluso con consultas
  activas. Persistencia por bot en `data/daily/manual_completed_days.json`,
  independiente de SQLite y del estado real. Las marcas cuentan para completar
  el mes en Vista general y habilitar SharePoint, con días verificados y manuales
  separados. Los pendientes siguen entrando en **Reintentar mes/día** aunque el
  día esté verde; las marcas se conservan al reintentar. La app activa se mantuvo
  abierta; este cambio se carga en el próximo arranque.
- Contención en lecturas de la lista corregida el 16/10: un `view` en segundo
  plano con SQLITE_BUSY/LOCKED se difiere al próximo refresco, sin declarar fallo
  del motor. Qt conserva filas/offset, ejecución y estado; un error real del motor
  no se borra al recargar la lista. La instancia activa se conservó; este ajuste
  se carga en el próximo arranque. Cuatro pruebas nuevas offline pasaron.
- Carga DUA tras cierre inesperado corregida: `chc_runtime/sqlite_recovery.py`
  recupera únicamente `SQLITE_READONLY_ROLLBACK` antes de las vistas de lectura.
  Exige lote libre y respaldo byte a byte; no rearma reservas ni migra esquemas.
  Detalles real recuperado el 16/10 con 52.154 guardados y contenido confirmado
  íntegro; nueve pruebas offline pasaron. Ver evidencia en el historial siguiente.
- Inicio mensual conjunto con selección de bots/procedimientos y trabajadores.
  Los cuatro DUA tienen proveedor/calendario diario, tres intentos automáticos
  persistentes y reintentos explícitos por día/mes. BLs conserva checkpoints por
  página y validación antes de reanudar.
- Diario DUA continuo confirmado el 16/10: Iniciar retoma el primer día pendiente;
  Desde/Hasta y Calendario avanzan sin cambiar el origen persistido. Continúa tras
  el rango elegido hasta ayer y espera a las 00:01 de Costa Rica. La app no inicia
  consultas al abrir. Inicio conjunto por mes y reintentos explícitos acotados.
- Bitácora: la comprobación automática de Detalles exige todos los DUAs guardados; los demás admiten omitidos
  fuera del resultado final. **Al día** cubre hasta la última fecha consultable.
  **Cierre manual…** es reversible, no altera SQLite y se invalida al cambiar
  datos/intentos. Por petición del 17/10, el cierre manual acepta pendientes en
  todos los bots, incluido Detalles. BLs y los cinco procedimientos de Manifiestos
  usan este cierre mensual; los cuatro DUA también aceptan las marcas diarias.
  Estas últimas no caducan con nuevos intentos y no modifican el motor.
- SharePoint opcional mediante OAuth2/PKCE y el registro CHC REPORTES existente.
  Una carpeta madre local y una online; solo CSV públicos, nombres en mayúsculas
  y subcarpetas por bot/procedimiento y mes. BLs separa mes/modo reales.
  Subidas únicamente por acción explícita, para bots completos, al día o cerrados
  manualmente. La navegación sitio → biblioteca → subcarpeta está corregida y
  comprobada con la cuenta real; una carpeta sin subcarpetas también se puede elegir.
- Git: el trabajo previo a SharePoint está en `main`/`origin/main` (`93ceb44`).
  La integración y correcciones continúan en `feature/sharepoint-oauth2`;
  la corrección del selector está en `bdf2bcd`. Mantener la rama separada hasta
  que el usuario solicite integrar. Código, pruebas, instaladores y documentación
  son versionables; tokens DPAPI, rutas elegidas, bases, resultados y runtime no.
- Validación ya realizada: 19 pruebas cloud, dos de Qt/DPAPI, cuatro del contrato
  de salidas, 17 de bitácora, una de bitácora Qt y 12 integraciones de exportación/
  recuperación de los seis bots, además del smoke QML. Lectura/escritura real de
  SharePoint comprobada con un archivo de prueba; no acredita actualización de Power BI.
- Pendientes: distribución ejecutable/equipo limpio, más variantes reales,
  calendario diario continuo de BLs y generadores/separadores todavía externos.

Guías vigentes: `README.md`, `workbench/README.md` y `docs/SHAREPOINT.md`.
Los apartados siguientes son el historial de las entregas y pueden describir
reglas anteriores; este resumen y las guías vigentes tienen prioridad.

## Historial de implementación

Actualización acumulativa de Manifiestos, 17/10: el usuario preguntó por descargar
Marítimo/Aéreo de octubre al 17 y completar al 1 de noviembre sin repetir datos.
Antes el rango/modalidades formaban la identidad y las colas congelaban el listado.
Ahora los cinco procedimientos sin IDs/límite comparten identidad mensual por
Courier; se conserva el lote compatible, incluso con nombre antiguo, y se procesan
solo novedades y pendientes de la consulta actual. Selecciones filtradas siguen
aisladas; bases históricas independientes no se fusionan automáticamente.

`manifest_incremental.py` adapta los stores en el proceso propio de Manifiestos.
Agrega jobs con ordinales estables, conserva resultados/intentos/exclusiones/
parciales y valida la familia de mes/modalidad/filtros antes de ampliar. La primera
adaptación crea respaldo SQLite en `data/backups/` fuera de `data/jobs/` para no
ofrecerlo como fuente. `manifest_adapters.py` conserva la reparación de identidades
antes del append y valida el listado principal contra las identidades confirmadas.
El listado agrega filas; los cuatro procesos con detalle conservan los Guardado.

`manifest_coverage.py` comprueba cantidad y firma de miembros, existencia de jobs,
resultados y fin de consulta. Une únicamente fechas acreditadas por modalidad,
conservando huecos y el corte de 00:01 Costa Rica; la cobertura legada se limita
a su primera selección. `MonthlyReader` y `KnowledgeSource` usan ese historial.
BLs sigue exigiendo trabajos Guardado y ausencia de páginas parciales; Courier N
puede alimentar BLs pero no acredita una descarga sin filtro en la bitácora.
La unidad guardada sigue siendo el manifiesto: no se vuelven a extraer detalles
confirmados para detectar cambios internos posteriores. El motor BLs mantiene
su identidad de entrada; esta entrega no convierte bases BLs diferentes en un lote.

CSV canónico mensual por modo: un parcial sustituido del mismo propietario/mes/
modalidad deja de ser salida final; no se borra el archivo. SharePoint pausa los
envíos antiguos sustituidos y solo sube el acumulado por acción explícita; no borra
históricos remotos ni cambia otras modalidades/propietarios.

Validación: 62 pruebas offline (7 nuevas de acumulación/recuperación/cobertura,
matriz Qt→cinco workers→portal local con ampliación por modalidad/reapertura,
entrega de base BLs, nombres, bitácora, Qt, inicio mensual, exportaciones y 20 cloud).
Guardados mantienen intentos/datos, nuevos IDs se agregan una sola vez y no hay
CSV duplicados. Verificador de copia correcto: 166 archivos y 138 sintaxis,
reporte local `runtime/diagnostics/validacion-copia-acumulacion-manifiestos.json`.
Se abrió Workbench en Vista general antes de documentar, sin iniciar consultas
reales; se mantuvo esa ventana abierta. Cambios completos disponibles al próximo
arranque. No se hicieron consultas de prueba a TICA ni subidas reales a SharePoint.

Conteo visible de días añadido el 17/10 por petición del usuario: solo números,
medianos/grandes y blancos. `MonthlyLog.qml` muestra `displayDays/daysInMonth`
junto al nombre de cada bot. `MonthlyReader` expone esos datos de presentación
desde la cobertura ya calculada; para cierres mensuales manuales cuenta los días
disponibles aceptados y para Manifiestos intersecta fechas entre modalidades y
procedimientos. No cambia estados, recuperación, reintentos ni habilitación cloud.
Dos comprobaciones Qt offline pasaron, con 16/31 y mes de 30 días, marca manual,
actualización, dos anchos y temas claro/oscuro. Capturas aisladas verificadas antes
de documentar en `runtime/diagnostics/bitacora-contador-dias-20261017*.png`.
Se conservó la app abierta y sus consultas; disponible al próximo arranque.

Aceptación manual global ampliada el 17/10 por instrucción expresa del usuario,
que sustituye la limitación visual de `04c3c0d` y la restricción anterior de
Detalles para cierres manuales. Marcar un día en el calendario ahora cuenta para
completar el mes del bot en Vista general y habilitar su CSV para SharePoint,
conservando sus pendientes y el comportamiento del reintento explícito.

`MonthlyReader` lee las marcas de los cuatro DUA sin importar motores ni escribir
SQLite. Cuenta las excepciones solo en los días aceptados y distingue cobertura
verificada/manual; también reconoce días aceptados sin base, sin crear resultados.
Un mes pasado cubierto aparece «Completado manual»; el actual, «Al día (manual)»
hasta la fecha consultable. Quitar una marca revierte la aceptación de ese día.
Un trabajo activo o una fuente de resultados ilegible siguen bloqueando la subida.
El cierre mensual explícito admite pendientes en los seis bots y los cinco
procedimientos de Manifiestos; conserva su huella e invalidación al cambiar datos.
Las marcas individuales del calendario persisten al reintentar.

La señal `calendarMarksChanged` refresca la bitácora al guardar/quitar una marca.
Tras su lectura, la cuenta SharePoint conectada refresca la lista local de meses
subibles. Los envíos siguen exigiendo **Subir a SharePoint** o reintento explícito.
No se cambiaron motores, fuentes, calendario operativo, resultados ni CSV.
La app abierta se conservó; la actualización se carga en el próximo arranque.
Pruebas offline: 24 de cobertura/cierre/aceptación global (incluidas siete nuevas
con Graph simulado), 19 cloud, ocho de Qt/calendario/configuración y el worker
Talón ampliado: su día verde sigue completo en bitácora tras reintentar únicamente
el pendiente. SQLite permanece idéntica al marcar/quitar, y el CSV simulado se envía
byte a byte solo por acción explícita en los diez destinos bot/procedimiento.
Captura aislada `runtime/diagnostics/mes-completado-manual-20261017.png`, verificada
antes de documentar; sin consultas de prueba a TICA ni envíos reales a SharePoint.

Marca manual diaria añadida el 17/10 por petición del usuario tras revisar Talón:
solo el 04/10 tenía todos sus DUAs guardados; los demás días atendidos conservaban
pendientes sin filas de tributos o con timeout. El usuario pidió poder marcar
un día en verde sin impedir que Reintentar mes consulte esos pendientes.

`workbench/daily_marks.py` guarda las decisiones visuales por bot con reemplazo
atómico. `DetailsBridge.daily` agrega `manualCompleted` sin modificar la respuesta
del worker, sus contadores ni sus órdenes; el botón no requiere detener consultas.
`DailyCalendar.qml` muestra el verde y «Completado manual» conservando estado real,
cantidades y error; permite quitar la marca. No se cambiaron coordinador, motores,
esquemas SQLite, CSV, cobertura, bitácora mensual ni fuentes copiadas.

Siete pruebas offline pasaron: cuatro nuevas de persistencia, separación por bot,
fallos de escritura/lectura, marca durante ejecución y acciones QML; dos existentes
de rangos/configuración QML; y el ciclo real del worker Talón con fixture local,
ampliado para marcar un omitido, reintentar el mes y reabrir. Los guardados y sus
intentos permanecen idénticos; solo los pendientes reciben nuevas oportunidades.
Captura aislada `runtime/diagnostics/calendario-completado-manual-20261017.png`.
Se verificó QML antes de documentar y se conservaron los mismos procesos activos
de la app y Talón, sin reinicios ni consultas nuevas a TICA como prueba.

Revisión de «database is locked» en Detalles el 16/10, tras el cambio de continuidad.
El traceback de las 13:00:29 corresponde a `view` → `catalog.read_rows` al leer
`sqlite_master`; el lector superó su espera durante un guardado. No falló el
comando de descarga: el registro y SQLite confirman 63 guardados posteriores y
53.520 guardados totales en la comprobación de las 13:23, con cinco trabajos activos.
La GUI convertía cualquier error de consulta de la lista en «No se pudo completar
la operación» y mantenía el aviso incluso cuando la siguiente lectura funcionaba.

`worker.py` emite `view_deferred` solo ante SQLITE_BUSY/LOCKED (incluidos códigos
extendidos) en un `view` de segundo plano, y conserva `idle(readonly=True)` para
liberar únicamente esa lectura. El refresco existente vuelve a solicitarla sin
acumular lectores. No se cambiaron tiempos, modo de SQLite, commits ni reservas.
`details_bridge.py` mantiene el estado operativo ante errores de `view`, limpia
solo el error de lectura al aceptar una vista posterior y preserva fallos reales
del motor frente a respuestas tardías o errores secundarios de lectura.

Cuatro pruebas nuevas: dos ejercitan el protocolo real con bloqueo EXCLUSIVE en
una SQLite aislada, lectura posterior del dato confirmado y fallos que deben
seguir visibles; dos del puente cubren los cuatro perfiles, filas/offset,
refresco, estado activo, limpieza del aviso y conservación del fallo de escritura.
Sin consultas de prueba a TICA. Se mantuvo la instancia abierta y sus workers;
la corrección queda en disco para el próximo arranque y los avisos de esa instancia
pueden seguir visibles mientras conserva el código anterior en memoria.

Continuidad diaria y rango visible ajustados el 16/10 por petición del usuario.
`DailyCoordinator.snapshot` calcula `resumeDate`, `resumeEndDate` y `waitingForDay`
desde el calendario; la fecha inicial guardada sigue siendo el límite inferior
de búsqueda para no perder huecos. `DetallesPage.qml` sigue esas fechas y
`DailyCalendar.qml` actualiza la selección mientras no haya una edición manual.
Guardar trabajadores/configuración no persiste la vista móvil como un nuevo
origen. Las ediciones del usuario conservan prioridad hasta guardar o iniciar.

El diario normal sigue con los días disponibles después del rango elegido,
omite completados/omitidos y espera al siguiente 00:01 local cuando está al día.
Al reabrir no corre nada hasta Iniciar. `daily_run` admite `bounded=True` para
el inicio conjunto por mes; `month_launcher.py` lo envía tras confirmar su
configuración. Reintentar día/mes sigue acotado y conserva resultados e historial.
No se cambiaron fuentes originales, parsers, salidas ni la política de intentos.

Comprobaciones offline: seis de coordinador/intentos, dos QML (los cuatro
perfiles, selección móvil, origen estable y edición manual), once de inicio
mensual, reintento mensual Talón y ciclo local de los cuatro workers: dos días,
continuidad más allá de Hasta, cierre/reapertura, espera y ausencia de redescarga.
La prueba de reloj cubre 00:00/00:01 de Costa Rica y cambio de mes; el flujo mensual
acotado no incorpora días ajenos. La carga simultánea de parsers nativos excedió
el límite inicial del fixture; se verificaron los cuatro en secuencia aislada.

Por autorización del usuario se registraron los cuatro diarios que estaban
activos (Detalles, Tránsito, Talón y XMovimientos), se pidió Detener, se cerró
ordenadamente y se reabrió una sola vez antes de documentar. Se pulsó Iniciar
únicamente en esos cuatro. No se iniciaron consultas nuevas para probar; su
reanudación real fue la solicitada por el usuario. El registro local está en
`runtime/diagnostics/bots-activos-20261016.json` y `bots-reanudados-20261016.json`.

Corrección del 16/10: Detalles no cargaba y mostraba «attempt to write a readonly
database». El primer SELECT fallaba con `SQLITE_READONLY_ROLLBACK` (776), por un
journal pendiente desde el 15/10 a las 16:27, no por atributos de solo lectura.
Se reprodujo en copia física; la recuperación nativa SQLite dio `quick_check=ok`.
El arranque común de los cuatro DUA comprueba las tablas registradas antes de
las vistas `mode=ro`. Solo ante ese código específico adquiere `RunLock`, copia
base y auxiliares a `data/queues/backups/rollback-*`, abre con `mode=rw` sin crear
bases y permite el rollback nativo. No crea JobStore, cambia estados, reinicia
intentos ni inicia descargas; las vistas y la bitácora siguen siendo de lectura.
Errores de permisos reales y fallos de respaldo se propagan sin intentar reparar.

Validación: seis pruebas nuevas, con procesos terminados abruptamente y journal
real, respaldo idéntico, contenido SQL completo conservado, bloqueo de otro dueño,
fallo de respaldo, base inexistente y arranque del worker Detalles aislado/offline.
Tres pruebas de intentos/omitidos también pasaron; su fixture se adaptó al método
`local_root` ya existente. Sin consultas nuevas a TICA. El usuario autorizó cerrar
la ventana ociosa: cierre ordenado y una reapertura antes de documentar. El
arranque recuperó octubre26, con respaldo local
`bots/detalles/data/queues/backups/rollback-20261016-102903-jhaffvo5/`.
La base real y la copia recuperada producen el mismo SHA-256 de todo `iterdump`:
52.154 guardados, 4.630 pendientes, 37 reintentos y cinco reservas previas intactas.
Estas reservas solo se rearman al iniciar consultas. Integridad correcta y panel
sin error, captura local `runtime/diagnostics/detalles-recuperado-20261016.png`.
El primer respaldo físico de diagnóstico está en
`bots/detalles/data/queues/backups/readonly-20261016-102615/`.

Inicio mensual conjunto añadido el 13/10/2026. Vista general muestra **Iniciar bots
por mes → Elegir bots…** con mes/año, casillas de los cuatro DUA, cinco procedimientos
de Manifiestos y BLs, trabajadores independientes, modalidades y total. No hay
selección/inicio implícitos al abrir. `workbench/month_launcher.py` coordina únicamente
los bridges; `MonthStart.qml` es el formulario. No importa motores ni sustituye colas.
Meses terminados únicamente. DUA reutiliza daily_run con rango 1–último día y
configuración confirmada por requestId, revalidada antes del envío. Manifiestos
recibe el mes completo y filtros despejados, sin cambiar el procedimiento visible.
Los procesos ocupados se mantienen. BLs espera Conocimientos completo del mes y
modalidades exactos; admite observar una ejecución existente compatible sin detenerla.
Se rechazan bases parciales. El botón Detener cancela la planificación y solo detiene
trabajos propios; respuestas tardías, cambios de configuración, detención desde el
bot y cierre no pueden iniciar otra tarea. Las esperas de preparación tienen límite.
Las elecciones persisten al navegar, pero no son un calendario automático al reiniciar.
Pruebas: once casos de coordinación/errores/cancelación/cierre, una QML (casillas, cantidades,
mes, inicio/cancelación, dos anchos y temas) y dos recorridos con workers originales
aislados. DUA recupera un mes con 29 días vacíos ficticios confirmados y procesa el día
restante de forma local; los cuatro perfiles conservan intentos al repetir. Los cinco
procedimientos locales completos alimentan BLs; segunda ejecución conserva resultados
y la misma SQLite. El fixture negativo permanente también dejó BLs bloqueado correctamente.
El portal positivo se activa exclusivamente con `CHC_MANIFEST_FIXTURE_COMPLETE=1`
en procesos de prueba offline; fuentes y motores originales no se modificaron.
Smoke correcto; sin consultas a TICA ni inicio de un lote real durante verificación.
Se abrió la app en Vista general antes de documentar. Capturas aisladas en
`docs/preview/inicio-mensual*.png`. Uso y límites en el README del Workbench.

Corrección de actividad del 13/10/2026: al emitir `changed`, el QVariantList de
eventos volvía a asignarse a ListView y reiniciaba el scroll. `activity_model.py`
añade un QAbstractListModel estable por bot; inserta/recorta filas sin reiniciar
el modelo. `qml/components/ActivityView.qml` conserva los delegados visibles y
solo sigue novedades si estaba al inicio. Un Timer hijo cancela el seguimiento
al abandonar la página; desplazamiento y barra manual tienen prioridad. Se usa
en DetallesPage (los cuatro DUA) y en las seis vistas demo. Compatibilidad de
`events`, Limpiar vista y límites originales (2.000 reales/30 demo) conservada.
Las pruebas QML verificaron mensaje y offset con textos multilínea, actualizaciones
sin logs, ráfagas, repetidos, recorte del límite/final, seguimiento al inicio y
limpieza, sobre los cuatro DUA y seis demos. Pasaron dos pruebas nuevas, la de
configuración/inicio existente y smoke, con datos en memoria y sin TICA.
La app real estaba descargando en varios módulos: se conservó esa ventana y se
abrió/verificó la versión corregida en QML aislado antes de documentar. El cambio
se cargará al próximo arranque; no interrumpir consultas por un cambio visual.

Bitácora mensual añadida el 13/10/2026 por petición del usuario. Vista general
muestra meses del historial real, seis bots y detalle desplegable de los cinco
procedimientos de Manifiestos. `workbench/monthly_progress.py` utiliza lecturas
SQLite/JSON, sin motores ni cambios en datos; `monthly_bridge.py` actualiza desde
un hilo con refresco al entrar/manual, cada 30 segundos y eventos agrupados a 10 s.
Un mes pasado solo se marca Completado con cobertura mensual y resultados
verificados: calendario/días contra jobs para DUA, Mes original y cobertura de
Conocimientos para BLs, selección/EOF/resultados/finalización para Manifiestos.
Rangos parciales y filtros se distinguen; archivos manuales con nombre mensual
pueden quedar Lote listo, pero no acreditan mes completo. Un lote antiguo listo
no oculta ampliaciones pendientes ni una modalidad terminada oculta otra pendiente.
Fuentes ilegibles se señalan, datos sin mes identificable no se asignan por nombre
aproximado o fecha de creación. Demo excluida. Mes actual nunca se declara completo.
Pasaron nueve pruebas de cobertura/lectura y una QML con actualización asíncrona,
detalle, navegación, dos anchos y temas claro/oscuro, además del smoke existente.
Capturas aisladas en `docs/preview/bitacora-mensual*.png`; sin consultas a TICA.
La inspección de uso real mostró varios bots descargando. Se conservó la ventana
del usuario y sus workers; la versión nueva se abrió de forma aislada antes de
documentar. La bitácora se cargará en esa ventana al próximo arranque, sin detener
consultas para un cambio de interfaz. No se añadieron reinicios ni inicios automáticos.

Preferencia vigente del usuario: mantener la interfaz sencilla y cercana a la
clásica. Detalles abre directamente con Procesamiento y Configuración; Base de
datos se abre aparte. Exportación, actualización y compatibilidad clásica están
en Más; los parámetros técnicos quedan plegados. No repetir pruebas extensas
por cambios visuales: una comprobación breve basta; ampliar solo ante cambios
sensibles de motor, datos o recuperación.

Actualización visual del 13/10: Manifiestos muestra sus cinco procedimientos en
una barra horizontal que reutiliza `NavItem`, con iconos y selección similares a
la barra lateral. Cada procedimiento y BLs ofrecen Procesamiento y Configuración;
los parámetros avanzados quedan plegados. Historial, configuración y consultas
siguen independientes; cambiar de procedimiento no detiene otro. Las páginas
permiten desplazarse en ventanas pequeñas. Se verificaron los cinco accesos y las
dos vistas en temas claro/oscuro con almacenamiento aislado, sin TICA; pasó la
prueba QML existente Conocimientos → base → BLs. App actualizada abierta antes
de documentar. Capturas en `docs/preview/manifiestos-horizontal.png` y
`docs/preview/manifiestos-configuracion.png`.

Nombres automáticos de Manifiestos, 13/10: los cinco procedimientos generan
`mesYY` (por ejemplo `octubre26`, `enero27`) y muestran Tabla como solo lectura.
`chc_runtime/manifest_names.py` comparte selección y nombres entre Qt y worker,
sin cargar motores en la GUI. Las variantes llevan sufijos por modalidades,
intervalo, Courier, límite o IDs; nunca se publican selecciones diferentes encima
de otra. La misma selección/carpeta reutiliza el lote, incluso si cambian nombre,
hilos u orden de modalidades. Lotes históricos conservan identidad, rutas, nombre
y SQLite; no se fusionan ni migran resultados. BLs conserva sus nombres porque
puede reunir varios períodos. Pasaron tres pruebas offline de nombres/recuperación,
la prueba QML con Octubre 2026 → Enero 2027, las tres pruebas de integración de
Manifiestos y el smoke QML. App actualizada abierta antes de documentar.

Revisión BLs del 13/10: el panel recuperado mostraba hashes internos en la columna
Manifiesto/BL y los contadores pasaban a cero durante la preparación. El lote real
conservaba 18 BL Guardado con un intento y 34.835 pendientes; las dos entradas
preparadas compartían firma y SQLite. Los reintentos observados eran pendientes
por timeout, no BL confirmados repetidos. La revisión fue de solo lectura.
Se corrigieron `manifest_service.py` y QML: identidades originales desde payload,
fila de entrada, búsqueda por BL/manifiesto, eventos unificados por ordinal,
prioridad a trabajos en curso y contadores conservados durante prepare. El botón
muestra Continuar pendientes al retomar la misma selección. Ocho pruebas locales
pasaron: dos nuevas de presentación/reapertura parcial, tres BLs–Conocimientos y
tres de Manifiestos. Originales y datos operativos intactos; sin TICA. Se reabrió
una vez la app detenida, mediante cierre ordenado, en BLs antes de documentar.

Ampliación BLs del 13/10: el usuario pidió página, filas acumuladas por BL y
retomar el punto de interrupción. Implementado en `chc_runtime/bls_session.py`
y `bls_pages.py`, adaptadores sobre el motor original intacto. Página verificada
se persiste junto a `bls.sqlite3` en `bls_pages.sqlite3`, con la misma firma,
offset, EOF, filas y hash. Se conserva la reserva y se comprueba Detener antes
de guardar/confirmar. Reanudación por primera/última páginas verificadas y salto
al offset ancla; solo entonces sigue la siguiente. Cambios de contenido o de
paginación conservan el avance y dejan el BL pendiente para revisión. EOF lleno
repetido se verifica; parciales nunca entran al CSV confirmado. Datos/namespaces
y concurrencia por trabajador permanecen separados.
QML muestra Página y acumulación por BL; el total general indica filas confirmadas.
Recuperación se activa con Continuar pendientes, sin inicio automático al abrir.
Legacy Guardado sigue intacto; Página «—» cuando nunca se guardó por páginas.
Pasaron nueve pruebas del portal local, una de presentación y cuatro de conexión
BLs/reapertura; captura aislada `docs/preview/bls-paginas.png` sin advertencias.
Sin TICA nuevo; más variantes reales siguen pendientes. Se reabrió una sola vez
la app detenida en BLs antes de documentar, mediante cierre ordenado.

Objetivo del usuario, decisiones aceptadas y estado efectivo del repositorio.
Corrección adicional del 13/10: el usuario autorizó revisar en TICA los BLs
pendientes con timeout y reiniciar después de aplicar cambios. Diagnósticos
acotados y privados de las filas 19/20/22 verificaron una línea completa por BL.
TICA enviaba también GET al perder foco; el código esperaba solamente POST y
podía ignorar una coincidencia ya recibida. El adaptador registra antes de llenar,
acepta GET/POST validados y normaliza las propiedades GeneXus en `bls_search.py`;
conserva filtros, identidad, secuencia, esquema y mensajes como requisitos.
Pasaron 13 pruebas locales de búsqueda/páginas y cuatro de panel/conexión/reanudación.
También se validó con el nuevo parser la respuesta GET capturada en un timeout real.
Con la app detenida se respaldaron SQLite/checkpoints, sesión y CSV, y se confirmaron
solo esos tres diagnósticos completos mediante las reservas originales. El lote
`d0b9c747860c67b266dd488f` pasó de 45 BL/83 filas a 48 BL/86 filas; quedan 34.805
pendientes. Se verificó que todos los Guardado anteriores y sus filas quedaron
idénticos. Respaldo local: `bots/bls/data/backups/recuperacion-20261013-205135/`.
CSV interno/público actualizado; una única reapertura ordenada en BLs, sin lanzar
el lote completo. Diagnósticos bajo `bots/bls/data/diagnostics/`, sin publicarlos.
Fuentes originales verificadas intactas; adaptadores sin cambios en `bots/bls/src`.

Estado vigente al 13/10/2026: Detalles, Tránsito, Talón y XMovimientos están
integrados con el mismo soporte Python/SQLite y panel QML. También se integraron
BLs y Manifiestos: cinco procedimientos, creación local de bases BLs, importación
de progreso y una única instancia interactiva. Leer `INTEGRACION_MANIFIESTOS.md`.
La entrega nueva se comprobó con un portal local, sin nuevas consultas reales.
Talón y XMovimientos usan sus parsers v2 y la selección de cuatro regímenes de
`Total_DUAS - Importacion.xlsx`; reutilizan una caché común verificada, con
progreso independiente. Leer `INTEGRACION_IMPORTACION.md`: columnas originales,
paginación, agrupación de movimientos, comprobaciones y alcance real.
Incidente del 13/10: Detalles quedó con una reserva `005-2026-685571` activa por
horas y un worker huérfano bloqueando otra ventana. Se respaldó y recuperó el lote;
se añadieron límites del intento y limpieza, cierre de hilos acotado y protección
Windows de procesos hijos. Ver `INTEGRACION_DETALLES.md` para evidencia y límites.
Refuerzo posterior: otra reserva `001-2026-079444` impedía pasar a la segunda
ronda; la cancelación cooperativa anterior no liberó el intento. El supervisor
ahora usa esperas independientes (`bounded_result`) y solo él confirma SQLite;
acota también tareas residuales y cierre del driver. Todas las rondas usan los
hilos configurados. Se mantuvo la GUI y se reconectó solo Detalles: el DUA se guardó
y se observaron seis consultas simultáneas al retomar la ejecución del usuario.
Conservar la instancia del usuario mientras procesa: no repetir reinicios durante
verificaciones ni anunciar que puede reanudar antes de terminar los cambios.
Corrección posterior de Tránsito: la base real del 1 de octubre tiene 583 DUAs
TRANSITO verificados y formato equivalente al Excel original. Se corrigieron la
inicialización de atributos al entrar en la navegación común y la espera de LINEAS.
Un DUA real antes fallido guardó 3 líneas / 8 columnas en una salida de prueba
independiente; los 583 DUAs operativos se conservaron pendientes para el usuario.
Ver el incidente y su evidencia en `INTEGRACION_TRANSITO.md`.
Caso adicional confirmado: `001-2026-078194` termina en exactamente 50 líneas.
TICA repite esa última página con EOF confirmado; se corrigió la paginación para
aceptarla solo con identidad, contadores, filas y mensajes del servidor coherentes.
Reproducción real aislada y validación offline de su respuesta documentadas allí.
Contrato de salida vigente: Resultados contiene únicamente el CSV, dentro de una
carpeta con el nombre actual de la tabla. Sin UUID ni subcarpetas técnicas visibles.
Los TXT/JSON y diagnósticos se conservan internamente en `bots/detalles/data/exports/`.
Leer junto con `AGENTS.md` antes de continuar. Fecha: 13 de octubre de 2026.

## 1. Qué quiere lograr el usuario

El usuario utiliza varios bots para consultar el portal TICA. Quiere unificarlos
en **CHC Workbench**, una plataforma modular con interfaz moderna y panel lateral
expandible para acceder a cada bot de manera independiente. La plataforma y los
bots deben vivir en `D:/CHC_CONSULTORES/Repositorios/CHC_AUTOMATIZACION_TICA`.

Las metas finales son:

1. **Una aplicación de trabajo:** acceso a módulos, bases, lotes, estados,
   resultados y configuración desde el mismo Workbench.
2. **Un repositorio mantenible:** código organizado por responsabilidades,
   módulos independientes y servicios comunes donde hay compatibilidad real.
3. **Crecimiento modular:** añadir bots, scripts o herramientas mediante registros
   y contratos, sin rediseñar el núcleo ni copiar interfaces enteras.
4. **Independencia de aplicaciones auxiliares:** integrar generadores de bases
   y preparación para dejar de abrir otros programas y transferir Excel manualmente.
   Generar una base y consumirla desde uno o varios módulos dentro de la plataforma.
5. **Operación fiable:** preservar validaciones, datos como texto, ceros iniciales,
   resultados confirmados, reanudación y compatibilidad de exportaciones.
6. **Distribución propia:** instalación trasladable sin rutas, entornos virtuales
   ni repositorios de las aplicaciones originales.

No se busca solamente juntar accesos directos. Abrir interfaces existentes en
procesos separados puede ser una transición; el destino es una experiencia común
que utilice motores desacoplados de sus GUI anteriores.

## 2. Módulos iniciales y versiones correctas

| Módulo | Origen | Versión elegida | Destino |
| --- | --- | --- | --- |
| BLs | `BLs_BOT` | Código actual de la raíz | `bots/bls/` |
| Detalles | `Detalles_BOT` | Código actual de la raíz | `bots/detalles/` |
| DUAs Tránsito | `DuasTransito BOT` | Exclusivamente `v2/` | `bots/duas_transito/` |
| Talón | `Talon_BOT` | Exclusivamente `v2/` | `bots/talon/` |
| XMovimientos | `XMovimientos_BOT` | Exclusivamente `v2/` | `bots/xmovimientos/` |

Los orígenes están bajo `D:/CHC_CONSULTORES/Repositorios`. El nombre físico de
Tránsito tiene un espacio. El usuario aclaró expresamente que `v2/`, cuando
existe, contiene la versión requerida. Se aplanó solo ese nivel externo: su
`src/` pasa a la raíz del nuevo módulo. No recuperar los `src/` antiguos externos.

Se copió el estado actual en disco, incluidos cambios sin confirmar, no solo
HEAD. La evidencia queda en `docs/migration/`. Los originales se mantienen
intactos como referencia y operación existente.

## 3. Generadores de bases para integración posterior

Origen indicado: **`D:/PortafolioDesarrollador/DUAS_SCRAPPING`**.

Se revisó y después se copió/conectó para el piloto diario de Detalles. Guarda consultas verificadas
en SQLite y produce las listas Total, Tránsito e Importación con `NroDUA`. Debe
integrarse como proveedor de datasets con período, régimen, procedencia y cobertura.

El usuario confirmó la correspondencia exacta: `Total_DUAS.xlsx` alimenta
**Detalles**, `Total_DUAS - Transito.xlsx` alimenta **DUAs Tránsito**, y
`Total_DUAS - Importacion.xlsx` alimenta **XMovimientos y Talón**. Actualmente
genera estas bases de un mes terminado mediante una ejecución manual del generador.

La independencia solicitada incluye obtener las bases automáticamente desde cada
bot, sin selección de Excel, en modo mensual o por días ya pasados. En modo diario:
descargar ayer, procesar hasta terminar y esperar a las 00:01 del siguiente día
local (`America/Costa_Rica`); si al acabar hay otra fecha pasada elegible, continuar.
Recuperar días atrasados sin omitirlos, guardar progreso persistente y acumular
resultados en la tabla/CSV del mes consultado, sin duplicar ni sobrescribir éxitos.
El cambio de mes se determina por la fecha de los datos, no por cuándo acaba el bot.
Requisito completo, ejemplos y límites: [AUTOMATIZACION_DIARIA.md](AUTOMATIZACION_DIARIA.md).
Detalles tiene un piloto en `feature/detalles-base-diaria-calendario`: base propia
diaria, calendario, espera de 00:01 y acumulación mensual. No inicia al abrir;
requiere Iniciar automático. Leer `PILOTO_DETALLES_DIARIO.md`. Posteriormente se
integraron Tránsito, Talón y XMovimientos con el mismo coordinador y contratos.

Alcance posterior: el usuario pidió adaptar DUAs Tránsito con la tecnología y
estructura de Detalles. Ambos usan ahora `chc_runtime/`, workers aislados y el
mismo puente/componente QML. Tránsito conserva el parser de v2, ocho columnas y
varias líneas por DUA; guarda todas las páginas juntas en SQLite y exporta sus
líneas al CSV mensual. El proveedor recibe selección TRANSITO para este módulo,
no los nueve regímenes de Detalles. Datos y ajustes quedan separados por bot.
Leer `INTEGRACION_TRANSITO.md`: archivos, uso, compatibilidad, pruebas y límites.
Su validación inicial fue offline; los incidentes reales posteriores y sus
correcciones están registrados en `INTEGRACION_TRANSITO.md`.

Talón y XMovimientos también comparten `chc_runtime/`, con parsers propios:
Talón usa LIQDUA y el resumen de siete columnas Sftributos1; XMovimientos usa
MANAERMAR y agrupa/suma bultos en seis columnas. La base automática común vive en
`integrations/duas_source/data/importacion/bases.sqlite3`; el bloqueo del proveedor
evita descargas duplicadas. Cada bot conserva su calendario, cola SQLite,
configuración, proceso y CSV mensual. Los cuatro bots heredan el supervisor que
libera intentos bloqueados sin esperar indefinidamente su cancelación.

El usuario autorizó revisar EXPORTACION TEMPORAL únicamente del 11/10/2026.
TICA confirmó cero registros. Se corrigió la copia del proveedor para acreditar
vacíos mediante la respuesta de Confirmar, con CAPTCHA aceptado, fechas/régimen,
contadores y ausencia de errores verificados. Aplica a los nueve regímenes:
uno vacío no impide crear la base con los demás; todos vacíos confirmados también
acreditan el día. Un error nunca cuenta como vacío. Ver los criterios y pruebas
en `PILOTO_DETALLES_DIARIO.md`; la diferencia en el extractor respecto de su
manifiesto inicial es intencional. El generador original no se modificó.

BLs necesita la base BLS de Conocimientos/Manifiestos. Es distinta de las listas
DUA: cinco columnas de texto descritas en `docs/INVENTARIO.md`. La ruta de ese
proveedor y los demás scripts aún deben inventariarse; DUAS_SCRAPPING no resuelve
todas las entradas por sí solo.

Los motores deberán consumir datasets internos o SQLite directamente. Excel/CSV
permanecerán como formatos de compatibilidad, sin ser el paso obligatorio de
coordinación entre aplicaciones. La dependencia de TICA y un navegador permanece.

## 4. Decisión tecnológica de la interfaz

- **Python:** lógica de aplicación, automatización y motores existentes.
- **PySide6:** conexión entre objetos Python y Qt.
- **Qt Quick/QML:** pantallas, navegación, layouts, controles y transiciones.
- **SQLite:** persistencia local prevista; BLs/Detalles ya la usan.
- **Playwright:** motor activo de los cinco bots copiados. DUAS_SCRAPPING mantiene
  Selenium/Edge y requerirá su propia decisión de migración.

Aplicación de escritorio para Windows local, sin servidor web o frontend React.
No introducirlos por defecto. Si el usuario cambia a acceso multiusuario desde
navegador, revisar esa decisión con el nuevo alcance.

El panel tiene un entorno propio `workbench/.venv/` y requiere
`PySide6-Essentials==6.12.0`. No reutilizar entornos de otras aplicaciones ni
mezclar requisitos de todos los motores sin validarlos.

## 5. Estado real implementado

**Completado:**

- Plan de implementación y arquitectura futura.
- Cinco módulos: 127 archivos copiados, más once ejemplos/requisitos nuevos;
  138 archivos de módulos en la línea base SHA256.
- Registro `workbench/modules.json` con IDs y rutas relativas.
- Herramientas de importación y comprobación de integridad.
- Panel QML con barra expandible, búsqueda y temas claro/oscuro.
- Vista general y cinco espacios de prueba independientes.
- Backend sintético en memoria con carga de ejemplo, simulación, pausa,
  continuación, reinicio, progreso, resultados de muestra y actividad.
- Instalación/apertura mediante BAT y modos de verificación/captura.
- **Detalles integrado:** panel QML operativo y worker con entorno propio,
  importación/append, catálogo SQLite, consultas, detención, configuración,
  filtros, gestión con respaldos, 38 columnas y exportación recuperable.
- Preferencia de tema persistente y sesión del módulo conservada.
- Interfaz clásica de la copia como compatibilidad temporal, usando los mismos datos.
- 50 pruebas existentes y cinco de integración Qt/proceso/SQLite satisfactorias.
- Prueba real de dos DUAs originales: 38 columnas idénticas, sin repetir guardados.
  Tabla de validación instalada en el módulo nuevo; originales intactos.

Detalles de funciones, límites y evidencia: `docs/INTEGRACION_DETALLES.md`.

**Todavía pendiente:**

- Ampliar opciones avanzadas de BLs cuando se necesiten; su motor ya está integrado.
- Ampliar generación mensual desde el Workbench y validar más variantes reales
  del portal para los cuatro consumidores DUA ya integrados.
- Coordinar procesos, eventos, lotes, errores y concurrencia global.
- Desacoplar GUI antiguas y convertir imports a namespaces propios.
- Integrar los otros generadores/separadores y ampliar la caché compartida.
- Validar distribución de los cuatro motores integrados en un equipo limpio.
- Empaquetar la plataforma y comprobarla en un equipo limpio.

`docs/ESTADO_INICIAL.md` es la entrega histórica de copia. La situación actual del
panel está aquí y en `workbench/README.md`. Una simulación o pantalla terminada
no demuestra integración, instalación o comportamiento real del portal.

## 6. Alcance vigente y autorizaciones

La restricción inicial de trabajar solo en el prototipo fue ampliada por el usuario:
**conectar y hacer funcionar Detalles**, sin olvidar ninguna función del bot actual,
incluso mediante compatibilidad temporal. También autorizó usar sus bases originales
como prueba. Estas instrucciones posteriores prevalecen sobre la etapa de demo.

- La integración autorizada incluye Detalles, DUAs Tránsito, Talón, XMovimientos,
  BLs y los cinco procedimientos de Manifiestos con su generador de bases.
  BLs ya tiene un adaptador independiente. Los parsers v2 copiados permanecen intactos;
  el motor del Workbench utiliza los perfiles y servicios comunes.
- El usuario autorizó subir el estado actual a Git y crear la rama del piloto diario
  con proveedor propio y calendario. Datos, ajustes personales, entornos virtuales
  y binarios permanecen fuera de Git; las comprobaciones nuevas fueron offline.
- Los originales se leen como referencia, sin modificar fuentes, datos o entornos.
- La prueba real de esta entrega se limitó a dos DUAs, una ronda y un trabajador,
  en almacenamiento propio. Ambos resultados coinciden con el original.
- No se migró ni ejecutó la base completa de 72.290 DUAs. Una prueba pequeña no
  autoriza una descarga masiva automática como parte de validaciones rutinarias.
- El motor sigue aislado en un proceso; el backend de demo no importa `bots/`.
- Diferenciar siempre Detalles operativo de las cuatro demostraciones.
- Conservar motor, esquema y formatos actuales hasta que se autorice su refactorización.
- Las comprobaciones rutinarias de interfaz/proceso deben usar HTML local sin red.

No pedir de nuevo permiso para acciones ya autorizadas de la integración; progresar
con ese alcance y documentar comportamiento, pruebas y limitaciones reales.

## 7. Invariantes para integrar después

- BL, secuencia y DUA como texto, con ceros iniciales.
- Nombres, orden, esquema y clasificación de exportaciones compatibles.
- Resultado y éxito confirmados juntos. Un fallo no equivale a vacío validado.
- Índices de sesión o TXT históricos no demuestran resultados correctos.
- Importar o cambiar rutas no debe borrar ni sobrescribir progreso o resultados.
- Aislar módulos: hoy comparten nombres globales `core`, `utils`, `flows`, `ui`.
  No cargarlos juntos en un proceso hasta resolver sus namespaces.
- Tránsito/Talón/XMovimientos ya usan persistencia transaccional en el Workbench;
  no convertir sus índices/CSV históricos en prueba de éxito completo.
- Actualizar QML mediante eventos; no bloquear la interfaz con trabajos.
- Definir concurrencia global y conservar perfiles/cookies aislados.
- Los specs archivados de v2 contienen rutas antiguas: adaptar y validar antes
  de usar como compilación del monorepo.

## Incorporación de Manifiestos, BLs e instancia única — 13/10/2026

El usuario autorizó integrar `D:/PortafolioDesarrollador/Manifiestos_Bot2` manteniendo
su funcionamiento. También pidió una única instancia del Workbench. Implementado:
Manifiestos, Conocimientos, DUAs por manifiesto, Movimientos y Contenedores, con
configuración e historial independientes; generador de bases BLs y envío directo al
módulo BLs, cuyo motor pasa de demo a operativo. Tabla/Contenedores añaden SQLite;
los otros tres mantienen sus colas originales y sus excepciones. Los 28 archivos
Python copiados están intactos; la documentación original está en `docs/reference/`.

La GUI sigue siendo QML sencilla. Motores por proceso y protocolo JSONL en
`chc_runtime/batch_worker.py`, adaptación en `manifest_service.py`/`manifest_adapters.py`,
puente en `workbench/batch_bridge.py`. La interfaz no importa fuentes ni entornos de bots.
No usar el perfil DUA para estos procedimientos ni mezclar Movimientos con XMovimientos.

Pruebas locales enfocadas: cinco procedimientos, reanudación, vacíos y errores,
exclusiones, cancelación, copia de progreso intacta, CSV ajenos protegidos,
generación de base y procesamiento BLs mediante botones QML. No se hicieron nuevas
consultas reales a TICA. Se abrió la versión integrada antes de documentar y se
comprobó que una segunda apertura conserva la misma ventana.

Leer `INTEGRACION_MANIFIESTOS.md` y `bots/manifiestos/AGENTS.md` antes de cambios.
Pendiente: automatización diaria continua y calendario de Manifiestos/BLs, pruebas
reales acotadas de esta integración y ampliación de opciones avanzadas de BLs si se
necesitan. Los calendarios de los cuatro bots DUA permanecen operativos.

## 8. Cómo continuar desde otra sesión

Ampliación BLs del 13/10/2026: el usuario confirmó que la base generada desde
Conocimientos es su entrada y pidió usar meses/modalidades disponibles directamente.
Implementado **BLs → Desde Conocimientos → Elegir meses → Iniciar**: proveedor
aislado `bls_source`, disponibilidad verificada con SQLite y preparación automática
Courier=N antes de llamar al motor BLs original. Solo Marítimo/Aéreo; pendientes,
activos y selecciones limitadas no se ofrecen. Los rangos terminados se etiquetan
por sus días; no se presentan como meses completos. No hay inicio automático al
terminar Conocimientos: se actualiza el selector. Entrada manual y progreso previo
se conservan. Nuevas pruebas locales sin TICA, y versión actualizada abierta antes
de documentar. Leer `BLS_DESDE_CONOCIMIENTOS.md` para invariantes, rutas y alcance.

1. Leer este documento, `AGENTS.md`, README principal y manual del panel.
2. Revisar la nueva instrucción del usuario: pedir cambios visuales no autoriza
   automáticamente integrar o refactorizar motores.
3. Abrir `Abrir_Workbench.bat` o ejecutar la app con su entorno.
4. Continuar diseño desde `workbench/qml/` y `workbench/demo.py`.
   Detalles operativo usa `workbench/details_bridge.py`, `qml/DetallesPage.qml` y
   `bots/detalles/workbench_worker.py`; leer su matriz de funciones antes de cambiarlo.
5. Si se autoriza integrar, leer inventario e instrucciones del módulo elegido;
   definir contratos antes de cambiar el motor.
6. Registrar avances efectivos y limitaciones, sin confundirlos con el destino.

Comprobaciones disponibles sin bots:

```powershell
.\workbench\.venv\Scripts\python.exe workbench/app.py --smoke-test
.\workbench\.venv\Scripts\python.exe -m unittest discover -s workbench/tests -v
py -3.12 tools/verify_import.py --check-sources
```

La comprobación de copia compara la línea base inicial. Si una fase posterior
cambia motores de forma autorizada, documentar cambios y distinguirlos al verificar.
No reemplazar el manifiesto histórico para esconder diferencias. En esta integración
se agregaron adaptadores y archivos nuevos; las 138 fuentes/ejemplos iniciales
siguen coincidiendo con sus hashes y los originales siguen intactos.

## XMovimientos: vacíos y trabajo activo — 14/10/2026

A petición del usuario se consultaron tres pendientes de `octubre26`, una vez
cada uno y en almacenamiento aislado: `001-2026-078121`, `001-2026-078143`
y `002-2026-088749` (los dos primeros con NoMovimientosError; el tercero con
timeout). Los tres existen y devolvieron cero movimientos, identidad correcta,
sin paginación ni errores. Esta revisión no modificó la cola. Evidencia privada
en `runtime/xmovimientos_revision/20261014-001202/`.

El usuario después pidió registrar vacíos aparte de errores y admitir reconsultas.
Implementado en `chc_runtime/movement_empty.py`/`MovementsJobStore`: estado `empty`
con fecha/evidencia, cero filas CSV, historial conservado y sin reintentos automáticos
en cada ronda. Se verifican identidad, encabezado, cero filas y ausencia de mensajes
o paginación. Colas antiguas se amplían con respaldo/transacción y se reclasifican
solo desde HTML válido; no desde el tipo de excepción. **Base de datos → Reintentar
vacíos** consulta únicamente los elegidos o todos si no se seleccionan filas.
Incluye vacíos antiguos aún por verificar. Los días correspondientes se reabren;
el resultado nuevo pasa a Guardado/Vacío/Error según lo recibido. Los vacíos
confirmados permiten avanzar calendario y bitácora, contándose aparte de guardados.

Aplicación local: 679 vacíos clasificados, 881 DUAs y 2.028 filas confirmadas intactas;
todo el historial/cantidad de intentos permanece idéntico. Dos casos sin HTML se
presentan «Vacío por verificar», fuera de Errores; los otros errores y DUAs aún sin
consultar se conservan. Respaldo/comparación en `runtime/xmovimientos_revision/
migracion-vacios/`. No se volvió a consultar el lote real completo.

El usuario también pidió ver progreso BLs y priorizar trabajo activo. Los cuatro
bots DUA muestran DUAs en curso sobre Actividad sin mover el scroll del historial;
todos los procedimientos por manifiesto/BL muestran «Descargando ahora» y ordenan
Descargando antes del límite de 200 filas. BLs anuncia página 1 antes de esperar
la respuesta y muestra filas acumuladas/checkpoint. Los cambios simultáneos de
trabajador se emiten sin descartarlos por el límite temporal de notificaciones.

BLs conservaba 2.641 BL guardados y 4.578 filas. Se consultó aparte únicamente el
BL interrumpido `26560432` de `1-0-26360645-P036-02/09/26`: obtuvo una fila. Evidencia
en `runtime/bls_revision/20261014-011605/`, sin importarla al lote. No se reprodujo
ni se identificó la causa exacta de aquella parada: el log anterior no la guardó.
Ahora excepciones/motivo quedan persistentes en `bots/bls/data/logs/bls.log` e
historial; un error de acceso al JSON auxiliar en una notificación no aborta SQLite.
Se solicitó al usuario el mensaje de esa parada; no hubo respuesta durante el trabajo.

Validación: almacenamiento/migración/reconsulta/calendario, integración con portales
locales de Talón/XMovimientos, bitácora, QML de trabajo activo, scroll de Actividad,
BLs búsqueda/paginación/reanudación e inicio mensual. Smoke QML e integridad de
fuentes satisfactorios; parsers/copias originales intactos. App final abierta en
XMovimientos tras cierre ordenado sin consultas activas. Leer
`INTEGRACION_IMPORTACION.md` y `BLS_DESDE_CONOCIMIENTOS.md` antes de continuar.

### 14 de octubre de 2026: revisión visible y pendientes mensuales

Implementados `manual_review_data.py`, `chc_runtime/manual_review.py` y el
adaptador Qt `workbench/manual_review.py`: TICA en las filas sin guardar abre el
formulario nativo correspondiente al DUA, BL o consulta de Manifiestos. Proceso
aislado, navegador visible y cierre independiente; página conservada ante errores.
Lee SQLite sin mutar datos y guarda únicamente diagnósticos en
`data/manual_reviews`. No confirma descargas ni recorre todas las páginas.
La selección de detalle de BLs se comparte mediante `bls_search.py`; las utilidades
asíncronas comunes se extrajeron a `async_operations.py` sin importar parsers ajenos.

El modo diario de los cuatro bots de DUA limita a tres oportunidades persistentes
por pendiente, devuelve la oportunidad al cancelar y deja el día `omitted` cuando
se agota. También limita a tres las recuperaciones de una base pendiente. Sigue
al día siguiente y mantiene omitidos al reiniciar. `retry_month`/`retry_day`
rearman expresamente solo los pendientes del período, sin repetir guardados ni
alterar configuración. Calendario, filtro de omitidos y bitácora distinguen esos
casos; los días sin base también impiden una falsa finalización mensual.

Validación con portales locales y almacenamiento aislado: revisión de los cuatro
DUA, BLs y cuatro consultas de Manifiestos; identidad y ausencia de mutaciones;
presupuesto persistente, cancelación, avance al siguiente día y reintento mensual
real de Talón; botones QML durante descarga; bitácora, búsqueda/paginación BLs,
supervisión, calendario, estados vacíos, scroll y smoke QML. Sin consultas reales
nuevas ni cambios de prueba sobre bases de producción.

Esta entrega está en disco. La instancia abierta y sus workers siguen ejecutando
la versión anterior para conservar las descargas activas. Las nuevas opciones se
cargan al reabrir la aplicación; no se reinició la sesión del usuario.

Ampliación de revisión: **TICA / Abrir en TICA** también está disponible en las
filas guardadas de DUA, BLs y Manifiestos, y en el detalle del DUA. Solo se quitaron
las restricciones de visibilidad por estado: se conserva el mismo inspector de
solo lectura, sin extraer resultados a la base/CSV ni cambiar progreso.

### SharePoint opcional y respaldo Git

Por instrucción explícita se consolidó todo el trabajo anterior en `93ceb44`,
se avanzó `main` mediante fast-forward en su worktree limpio y se subió a
`origin/main`. Se creó `feature/sharepoint-oauth2` desde esa principal.

Implementado `chc_cloud/`, proceso `sharepoint_bridge.py` y diálogo **Cuenta y
SharePoint**: OAuth2/PKCE con MSAL, caché DPAPI, selección de sitio/biblioteca/
carpeta por bot o flujo y copia opcional de CSV. Eventos `published` tras exportar
localmente; outbox y cola SQLite durables, deduplicación, cuenta/destino capturados,
conflictos y actualizaciones condicionadas por `eTag`. Fallos cloud no modifican
descargas, SQLite de bots, calendario ni resultados locales. La app puede operar
sin cuenta y no inicia sesión automáticamente.

En la pestaña Entra abierta por el usuario se creó **CHC Workbench · Resultados
SharePoint**: cliente `da7ff4b7-8a2e-4c49-9338-17975a058a99`, directorio CHC
`f7015bc9-c229-413a-ab08-e1e5a76a09f1`, solo inquilino CHC, escritorio con retorno
`http://localhost`. Único permiso Graph `Sites.Selected` delegado, User.Read
predeterminado retirado, ningún secreto ni permiso de aplicación. Ver
`docs/SHAREPOINT.md` para asignar acceso `write` cuando se elija el sitio.

El usuario indicó que elegirá los destinos después. No se hizo login OAuth ni
subida real: falta autorización explícita al sitio y selección de carpeta.
Validación: 12 pruebas cloud, dos Qt/worker/DPAPI, dos integraciones Talón/XMov,
tres de Manifiestos (incluye cinco procedimientos y BLs), smoke QML y diff limpio.
La instancia anterior había sido cerrada por el usuario; app nueva abierta en
Vista general antes de documentar. Dependencias cloud instaladas solo en el
entorno Workbench; bots originales/copias preservados.

### Exploración de sitios y consentimiento de lectura

El usuario proporcionó la página **Bibliotecas** de CHC y autorizó expresamente
explorar todos los sitios a los que tenga acceso su cuenta. Se agregó
`Sites.Read.All` delegado a los ámbitos de la app, conservando `Sites.Selected`
para escritura. El usuario lo agregó manualmente en Entra; el botón de
consentimiento administrativo estaba deshabilitado.

Implementados catálogo Graph `/sites?search=...`, paginación, filtro al host CHC,
búsqueda por nombre y selección de sitio/biblioteca/carpeta. La URL
`/_layouts/15/sharepoint.aspx/onedrive/places` abre el catálogo; los enlaces
FileBrowser con id/listurl y Forms con RootFolder se normalizan al sitio real.
Se comprobaron en Edge seis entradas y sus URL, conservadas solo en runtime.

La sesión OAuth inicial del usuario está conectada; prueba real de lectura raíz
con `Sites.Selected` devolvió 403. Se renovó la conexión desde la app nueva y
Microsoft mostró **Se necesita la aprobación del administrador** para el ámbito
nuevo. Falta esa aprobación para comprobar sitios/bibliotecas/carpetas reales
por Graph. No subir resultados ni configurar destinos como parte de esta prueba.
15 pruebas cloud y dos Qt/worker/DPAPI, más smoke QML, pasaron. Se reabrió la app
una vez tras confirmar que sus procesos no tenían navegadores de bots activos.

### Registro reutilizado y comprobaciones reales satisfactorias

El usuario propuso usar **OAuth2 par CHC REPORTES**, cliente
`077e19a4-ab53-4e55-8286-ec02dc3cf36c`, y dejó su pestaña de permisos abierta.
Se comprobaron `Sites.Read.All` y `Files.ReadWrite.All` delegados y retornos de
escritorio existentes `http://localhost:62190/` y `http://localhost:5000`.
No se modificó ese registro. Workbench cambió al cliente existente y solicita
solo los dos ámbitos anteriores; no usa secretos ni permisos de correo/Power BI.
La conexión OAuth con la cuenta CHC fue satisfactoria. El bloqueo administrativo
del registro nuevo ya no aplica al cliente usado por la app.

Graph devolvió 7 sitios. Se leyeron bibliotecas y carpetas de Automatización TIC@
(Documentos, 15 carpetas originales) y TIC@_DUASxREGIMEN (Documents, 8). Se verificó
también el selector de la app con esos 7 sitios y Automatización TIC@ / Documentos.
El usuario autorizó expresamente una prueba de escritura con un archivo cualquiera:
se creó `CHC_Workbench_Prueba_20261014_163132/prueba_conexion.txt` en Automatización
TIC@ / Documentos, se subió y descargó idéntico; después se actualizó con eTag y se
comparó otra vez. Se conserva en SharePoint para revisión; informe privado en
`runtime/sharepoint-write-test/report.json`, enlace en `docs/SHAREPOINT.md`.

No se configuraron rutas de bots ni se enviaron CSV de producción. Se mantiene
la sesión conectada y la app abierta en el selector de esa biblioteca. 15 pruebas
cloud, dos Qt/worker/DPAPI y smoke pasaron; el registro nuevo inicial se conserva.

### Carpeta común, nombres estandarizados y subida exclusivamente manual

Alcance final solicitado: una sola carpeta madre local y una sola de SharePoint
para todos los bots, solo CSV públicos, nombres en mayúsculas con bot, mes/año y
modo cuando aplica. `chc_runtime/output_layout.py` define el contrato y registro
local común; `RESULTADOS/` es el valor predeterminado y queda fuera de Git.
Auxiliares y progreso permanecen internos. BLs separa sus filas por mes/modo real
del manifiesto. Selecciones parciales y lotes manuales conservan sufijos distintos.
Los históricos originales se conservan: **Exportar** los regenera desde SQLite
en la estructura común sin consultar TICA. Cambiar carpeta no mueve archivos.

La pantalla **Cuenta y resultados** reúne cuenta, carpeta local, carpeta online
y selector de mes. Elegir una carpeta no publica archivos. **Subir a SharePoint**
solo envía los CSV registrados de bots/procedimientos con ese mes cerrado y
completo verificado por `MonthlyReader`. No hay temporizador ni conexión de
eventos de exportación a subidas. Envíos fallidos requieren reintento explícito;
rutas por bot y avisos automáticos antiguos se conservan sin enviarlos.

Verificado: 18 pruebas cloud, dos Qt/DPAPI, cuatro del contrato de nombres y
12 integraciones de Detalles, Tránsito, Talón, XMovimientos, calendario diario,
cinco procedimientos de Manifiestos y BLs; smoke QML. La app actualizada quedó
abierta, con cuenta CHC conectada y destino común pendiente de elegir por el
usuario. No se subieron CSV de producción. README y `docs/SHAREPOINT.md` describen
el comportamiento vigente; los apartados anteriores registran su evolución.

Última aclaración del usuario: solo Detalles exige 100 % de DUAs guardados.
Los demás pueden completar excluyendo omitidos del resultado final, conservando
pendientes/páginas parciales para reintento. La bitácora incluye días omitidos
(y bases omitidas) para Tránsito/Talón/XMovimientos; Manifiestos y BLs admiten
exclusiones/intentos agotados en ejecuciones finalizadas, sin confundir una parada
con finalización. Mes actual pasa a **Al día** al cubrir hasta la última fecha
consultable, respetando 00:01 Costa Rica, y vuelve a comprobarse al avanzar fecha.

**Cierre manual…** en cada mes permite elegir bot/procedimiento y marcar completo
o restablecer comprobación automática. Metadatos separados en
`runtime/workbench/monthly_overrides.json`; no escribe en SQLite de bots.
Marca ligada a cobertura, contadores y revisión de intentos, invalidada al cambiar
datos. Detalles no permite cierre con DUAs sin guardar. SharePoint acepta estados
completos, al día y cierres manuales vigentes, solo mediante acción del usuario;
subir un mes no envía pendientes de otro mes. 19 pruebas cloud y 18 de bitácora/Qt
verifican las reglas vigentes, además de las integraciones de exportación anteriores.

### Corrección del selector de carpetas SharePoint

El usuario reportó bibliotecas visibles pero sin carpetas al elegirlas. Reproducido
en Qt: al cambiar el modelo desde el clic se destruía el delegado y aparecía
`ReferenceError: dialog is not defined`, interrumpiendo la petición. Navegación
movida a funciones del diálogo con identidad capturada antes del cambio de lista.
Prueba Qt recorre sitio/biblioteca/subcarpeta, notificaciones síncronas, carpeta sin
subcarpetas y selección correcta. App actualizada abierta antes de documentar;
cuenta real recorre Automatización TIC@ → Documentos y muestra sus carpetas.
No se guardó un destino ni se subieron resultados durante la comprobación.

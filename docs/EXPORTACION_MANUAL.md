# CSV de resultados: generación manual

Desde el 22/10/2026 los seis bots guardan sus avances y resultados confirmados en
SQLite. Consultar, reintentar, detener, importar progreso o cerrar una ejecución
ya no genera CSV de resultados, ni internos ni públicos. Los calendarios y la
reanudación siguen utilizando sus bases. Las bases de entrada y generadores no
se eliminan ni se sustituyen por CSV.

## Uso

- Para una tabla DUA: abrirla y elegir **Más → Generar CSV de esta tabla**.
- Para BLs o un procedimiento de Manifiestos: seleccionar la ejecución y elegir
  **Más → Generar CSV de esta ejecución**. Incluye sus modalidades admitidas.
- Para todos: en **Vista general**, debajo de la bitácora, pulsar
  **Generar todos los CSV**. Recorre las tablas y ejecuciones guardadas de todos
  los meses, sin cambiar la selección actual. Incluye resultados confirmados de
  lotes pendientes; el CSV por sí solo no acredita que un período esté completo.

La generación conjunta procesa los módulos de uno en uno para limitar el trabajo
de disco. Omite módulos ocupados, continúa con los demás y muestra los errores o
las omisiones al terminar. No detiene consultas ni inicia descargas. Cerrar la
ventana impide que se programen nuevas exportaciones de esa acción.

Las salidas conservan nombres, columnas, ceros, orden y separación por mes/modo.
BLs se reconstruye siempre desde SQLite, incluso si quedó un CSV interno antiguo.
Generar CSV no inicia ninguna subida a SharePoint. Sus acciones y condiciones de
cobertura siguen siendo independientes; generar primero los archivos que se
quieran subir. Un CSV generado manualmente permanece igual hasta otra generación.

## Propiedad y recuperación

Un CSV existente ya no bloquea **Iniciar consulta**: la consulta no lo escribe.
Al generar manualmente se mantienen las protecciones contra sobrescribir archivos
ajenos u otro lote. El registro durable de publicaciones en SQLite acredita al
propietario aunque falte el JSON auxiliar; ese era el conflicto observado en
Conocimientos de octubre. No se adopta un archivo solo por nombre o contenido.

Los CSV eliminados pueden reconstruirse desde sus resultados SQLite mediante las
acciones anteriores. No reintentar consultas para regenerar archivos.

## Entrega y verificación

Código `15a6fbc` en `feature/sharepoint-oauth2`. Aplicado a la instalación local de
C mediante 13 archivos de runtime/QML (256.881 bytes), con respaldo y manifiesto
de hashes actualizado en
`runtime/diagnostics/manual-csv/install-update/20261023T045603Z/`.
El instalador antiguo de `runtime/releases/` todavía contiene el payload anterior.

Pasaron 35 pruebas offline: cuatro bots DUA, cancelación/reanudación y exportación
conjunta de tablas; cinco procedimientos con portales locales; BLs incremental y
reconsulta de vacíos; propiedad del CSV con/sin JSON; coordinación conjunta,
cancelación/respuestas tardías; QML y geometría en 1280×774, 1000×680 y 1000×600.
Los primeros intentos fallaron por archivos no disponibles de OneDrive; se usaron
dependencias instaladas locales y entradas sintéticas temporales, sin modificar
fuentes originales. La instancia controlada de la instalación cargó los seis
módulos en 9,516 s, sin avisos QML ni CSV antes de una acción manual. No se
consultó TICA. La app instalada quedó abierta antes de documentar.

## Borrado solicitado: bloqueado

Se inventariaron 44 CSV regenerables públicos/internos y duplicados idénticos,
638.547.240 bytes. Se excluyeron bases de entrada, respaldos, diagnósticos y
archivos de compatibilidad sin verificación equivalente. **No se borró ninguno**:
la revisión automática rechazó la operación nativa con `blocked by policy`, sin
otro motivo. No se intentó eludir el bloqueo con otro intérprete.

Una primera prueba de carga dejó una copia temporal porque el lector mensual
seguía usando un archivo al limpiar. El arnés se corrigió para esperar al lector;
la segunda prueba terminó y retiró su almacenamiento. La limpieza posterior de
la copia anterior también fue rechazada automáticamente: siguen 147.710.122 bytes
en `%TEMP%/CHC-two-loads-2qxrzjw2`. No confundirla con datos activos de la app.

Plan, inventario y estado exacto: `runtime/diagnostics/manual-csv/`.
Capturas/informe de carga: `runtime/diagnostics/two-loads/full.json` y PNG cercanos.

# BLs conectado a Conocimientos

Implementado el 13/10/2026. BLs utiliza las descargas terminadas de Conocimientos
para preparar su propia base y ejecutar su motor actual. No es necesario generar
un Excel ni seleccionar un archivo intermedio para este recorrido.

## Uso

1. Descargar **Conocimientos asociados** desde Manifiestos y terminar sus pendientes.
   También puede importarse su progreso SQLite original desde Más, sin modificarlo.
2. Entrar en **BLs**, con origen **Desde Conocimientos**.
3. Pulsar **Elegir meses…** y marcar los períodos y modalidades disponibles.
   Pueden seleccionarse meses distintos y Marítimo/Aéreo juntos o por separado.
4. Pulsar **Iniciar consulta**. Se prepara la base Courier=N y luego empieza BLs.

La lista se actualiza al terminar o importar una descarga de Conocimientos y al
abrir el selector. Actualizar lee SQLite; no realiza consultas a TICA. Si todavía
no hay descargas terminadas, se informa y se ofrece ir a Conocimientos.
No se inventan opciones para meses o modalidades sin datos disponibles.

**Archivo externo** conserva la entrada manual Excel/SQLite, la selección de hoja
y los lotes anteriores. La elección manual del generador de bases de Manifiestos
también permanece disponible para sus usos específicos.

## Qué significa disponible

La comprobación lee una instantánea SQLite de Conocimientos; no se basa en CSV,
nombres de archivo, contadores de la interfaz ni el estado resumido del historial.
Se exige selección confirmada, todos sus trabajos Guardado, resultados confirmados,
ninguna página parcial y una ejecución finalizada correctamente.

Se aceptan únicamente Marítimo y Aéreo, descargados con todos los Courier o Courier N.
Se excluyen selecciones limitadas por IDs o cantidad de manifiestos, Courier S,
otros procedimientos, períodos futuros, trabajos pendientes/activos y fuentes sin
control suficiente para acreditar su finalización.

Un intervalo terminado dentro de un mes puede ofrecerse, pero muestra sus días
disponibles. **Mes completo** exige cobertura de todos sus días y que el mes haya
terminado. Se agrupan intervalos finalizados compatibles; no se presupone cobertura
de los días que faltan ni del resto de un mes en curso.

Desde el 17/10, las bases acumulativas de Conocimientos acreditan sus rangos con
el historial de consultas confirmadas de SQLite. Ampliar el mes añade manifiestos
sin repetir los Guardado; el proveedor BLs toma todos los resultados confirmados
y la unión exacta de rangos, conservando los huecos. El último intervalo elegido
en la pantalla no sustituye la prueba de cobertura mensual. Los respaldos de
migración se guardan fuera de los directorios de fuentes y no aparecen como bases.
Esto no modifica la firma del motor BLs ni convierte entradas diferentes en un
mismo lote de BLs: su recuperación y checkpoints conservan el contrato original.

Solo se utilizan los archivos propios del Workbench: descargas/importaciones en
`bots/manifiestos/data/jobs/conocimientos/` y SQLite de la copia clásica en
`bots/manifiestos/datos_app/SQLite/conocimientos/`. No se depende de las carpetas ni
de los procesos de la aplicación original. Para traer resultados antiguos debe
importarse explícitamente su progreso SQLite en Manifiestos.

## Preparación y descarga

Antes de crear la base se verifica nuevamente la disponibilidad. Se obtienen
copias SQLite consistentes mediante backup desde conexiones de solo lectura;
la validación y la copia corresponden a la misma instantánea. Los originales no
se modifican y los temporales se eliminan dentro de su carpeta propia verificada.

El generador original de Manifiestos conserva sus reglas: Courier=N explícito,
texto y ceros iniciales, orden, cinco columnas BLS, eliminación de duplicados
equivalentes y detección de BL contradictorios. La modalidad y fecha viajan en
cada IDManifiesto; el motor BLs mantiene sus fechas y validaciones por entrada.
Si aparecen inválidos o conflictos, este recorrido automático no inicia consultas
y conserva su auditoría para revisión.

Una descarga completa sin conocimientos, o sin ningún BL Courier N, se informa
como selección sin BLs. No se confunde con un fallo ni se inicia el navegador de
BLs. La auditoría registra `completed_empty`; no se simulan consultas exitosas.

La tabla del Workbench muestra la fila de entrada y los valores originales de
manifiesto/BL, leídos del payload SQLite. Los hashes permanecen internos. Buscar
filtra por manifiesto o BL original, conservando ceros. Los eventos del motor y
la recuperación SQLite actualizan una única fila por ordinal; mientras consulta
se priorizan los trabajos en curso. Preparar la base/navegador no reinicia los
contadores. Al retomar la misma selección con pendientes, el botón indica
**Continuar pendientes**.

## Página actual y recuperación dentro del BL

El Workbench añade **Página** y las filas acumuladas de cada BL. Mientras solicita
la página siguiente puede mostrar, por ejemplo, página 4 y seis filas guardadas
de las tres anteriores. La ayuda identifica la última página verificada. Al
detener o reabrir muestra esa página guardada y sus filas acumuladas. El contador
general conserva únicamente los resultados de BL completos; las páginas parciales
no se publican como éxitos ni se mezclan con el CSV confirmado.

El adaptador `chc_runtime/bls_session.py` extiende `BLSProcessor` y `TicaSession`
de la copia original. Conserva formulario, identidad exacta, cookies por sesión,
fechas por entrada, firmas, reservas, concurrencia, reintentos y exportaciones.
Las líneas usan HTTP de la misma sesión y el evento GeneXus GRID1PAGING/NEXT.
`bls_pages.py` valida identidad, secuencia, 18 columnas, contadores, offset, EOF
y números de línea sin repeticiones. Cada página completa se guarda en una
transacción en `SQLite/bls_pages.sqlite3`, junto al progreso `bls.sqlite3`, con
la misma firma de selección. Se comprueban la reserva y Detener antes de guardar
y antes de entregar el resultado completo al motor.

Al continuar se cargan páginas contiguas verificadas por su hash y se renueva el
formulario. Se contrastan la primera y última guardadas con las respuestas nuevas;
se salta a la última mediante su offset y se solicita la siguiente. No se vuelven
a acumular las páginas previas ni se consultan BL ya Guardado. Si el tamaño de
página, contenido, identidad, esquema o punto de reanudación cambió, se conserva
el avance y el BL queda pendiente para revisión. Una última página llena repetida
solo termina con EOF confirmado e identidad, filas y contadores coincidentes.
Incluso un cierre después de guardar EOF pero antes de confirmar Guardado se
recupera verificando esas páginas y entregando el resultado completo.

Esto aplica al avance guardado desde esta incorporación. La copia anterior solo
persistía el BL completo y rechazaba detalles paginados; no es posible reconstruir
una página antigua que nunca se guardó. Los confirmados antiguos siguen intactos
y muestran «—» en Página cuando no tienen ese historial. La recuperación requiere
la misma selección y lote; cambiar los datos mantiene la política original de
crear otra identidad. No se modificaron fuentes originales ni el ejecutable clásico.
La aplicación no inicia consultas por sí sola al abrir.

Verificación: nueve pruebas con navegador y portal HTTP locales cubren fallo
después de tres páginas, reanudación mediante ancla, pausa, EOF repetido, vacío
confirmado, cierre tras EOF, dos BL simultáneos, avance dañado y respuesta tardía
tras Detener. Pasaron también la prueba de presentación/recuperación y las cuatro
pruebas BLs–Conocimientos/reapertura parcial. La captura QML muestra dos páginas
y 75 filas parciales en almacenamiento temporal, con contadores separados y sin
advertencias: [vista de prueba](preview/bls-paginas.png). No se hicieron consultas
reales nuevas a TICA; quedan por contrastar más variantes reales del portal.

Se conserva una base privada verificada por hash para cada versión de los datos.
La misma selección sin cambios reutiliza la preparación y la identidad original
del lote; BLs retoma pendientes y no repite guardados. Se conserva también un lote
manual previo si su entrada normalizada, destino e identidad son equivalentes.
Si los datos cambian, el motor mantiene su regla original de crear otro lote.
Con nombre automático se usan carpetas legibles por meses/modalidades, con sufijo
numérico si hace falta conservar otra versión. Un nombre escrito por el usuario
mantiene las protecciones existentes contra sobrescribir otro lote.

**Detener** sirve tanto al preparar la base como durante las consultas. Un resultado
de preparación que llegue después de detener o cerrar no puede iniciar BLs.
Las descargas de Conocimientos no arrancan automáticamente el bot: actualizan lo
disponible, y el usuario decide su selección e inicio.

## Arquitectura y mantenimiento

- `chc_runtime/knowledge_source.py`: disponibilidad, instantáneas, caché y generación.
- `batch_worker.py --flow bls_source`: proveedor aislado en el entorno de Manifiestos.
- `manifest_service.py`: comandos del proveedor y adaptación de lotes BLs.
- `workbench/batch_bridge.py`: preparación → descarga, cancelación y errores entre procesos.
- `qml/BlsKnowledgeDialog.qml`: meses y modalidades reales; `ManifiestosPage.qml`: origen e inicio.
- `workbench/app.py`: actualización al finalizar/importar Conocimientos.

El proceso BLs conserva `bots/bls/src/core/engine.py`, sus parsers, reservas por
token, reintentos y exportaciones. No importa fuentes de Manifiestos en ese
proceso. El proveedor usa el entorno de Manifiestos y su sesión independiente
`data/workbench/bls_source/`, separada del generador manual `bases`.

Bases verificadas y auditorías: `bots/manifiestos/data/bls_source/`. El JSON junto
a cada base registra selección, fuentes, cobertura, hash y auditoría. Los CSV de
BLs siguen publicados únicamente en `bots/bls/resultados/<nombre de tabla>/`.
No hay pasos de preparación técnicos en esas carpetas públicas.

No se modificaron las fuentes originales de BLs ni de Manifiestos. No requiere
paquetes adicionales a sus entornos ya instalados. Esta incorporación no añade
un calendario diario continuo para BLs.

## Comprobaciones realizadas

Pruebas locales y temporales, sin consultas reales nuevas a TICA:

- Disponibilidad real desde SQLite, separando Marítimo/Aéreo y descartando
  pendientes, ejecuciones activas, selecciones limitadas, Courier S y Terrestre.
- Intervalos parciales identificados; selección conjunta y cambio de mes/modo.
- Base generada → lector/motor BLs original → SQLite/CSV, conservando un BL de
  23 dígitos con ceros y la identidad de cada modalidad.
- Reanudación de la misma entrada con un intento por BL guardado.
- SHA-256 de las fuentes intacto tras preparar y procesar la base.
- Período no disponible rechazado antes de iniciar BLs; selección vacía válida sin consultas.
- Selección desde botones y casillas QML hasta el procesamiento, sin advertencias.
- Compatibilidad del recorrido manual anterior y smoke de las seis vistas.

Pruebas enfocadas: `workbench/tests/test_bls_knowledge.py` y
`test_bls_knowledge_qml.py`. No se ejecutaron lotes de producción como prueba.

Corrección del panel del 13/10: se estaban mostrando hashes al recuperar SQLite
y reiniciando los contadores durante `prepare`, aunque el motor sí conservaba
el progreso. La revisión de solo lectura del lote de septiembre encontró 18 BL
Guardado, todos con un intento, y 34.835 pendientes. Sus dos entradas preparadas
tenían la misma firma normalizada y las dos ejecuciones usaron la misma SQLite;
las filas 19/20 reintentadas seguían pendientes por timeout. No se modificó ese
progreso ni se hicieron consultas reales para verificarlo.

Pruebas nuevas: `chc_runtime/tests/test_bls_progress.py` verifica identidades,
búsqueda, actualización sin duplicados y contadores conservados sin escribir
SQLite; `workbench/tests/test_bls_resume.py` reabre un lote temporal con un BL
confirmado y otro pendiente, comprueba una sola base y un intento por cada BL.
También pasaron las tres pruebas de conexión BLs–Conocimientos y las tres de
integración de Manifiestos. Se abrió BLs actualizado mediante un cierre ordenado
único, después de comprobar la app detenida y sin navegadores de consulta activos.
El motor original y su firma permanecen intactos; no se recompiló el ejecutable
clásico porque la corrección está en el adaptador del Workbench y QML.

## Recuperación por página y búsquedas GET/POST — 13/10

El adaptador `bls_session.py` mantiene las páginas verificadas en `bls_pages.sqlite3`,
junto al progreso original. Comprueba primera/última páginas antes de continuar;
un BL parcial conserva sus filas y permanece pendiente hasta verificar EOF.
La interfaz distingue filas acumuladas por BL de filas confirmadas del lote.

Después de la revisión anterior, el usuario pidió comprobar en TICA las filas
19, 20 y 22 del lote de septiembre con varios intentos y reiniciar la app tras
corregir. Los tres BL existen y cada uno devolvió una línea completa verificable.
La causa observada fue esperar exclusivamente el POST de Confirmar: TICA también
refresca la búsqueda por GET al perder foco, a veces antes de registrar la espera.
Ese timeout no acredita ausencia ni falta de datos.

`bls_search.py` acepta los filtros devueltos en `gxValues` y las 24 propiedades
de cada fila GET, y conserva el parser de identidad/enlace original. Se rechazan
mensajes, otro período/BL, ámbitos ambiguos, cantidades incompatibles y cambios
de columnas. El listener se registra antes de llenar; la respuesta POST sigue
admitida con las validaciones originales. La falta de respuesta verificable deja
un error explicativo y conserva el progreso, sin confirmar un vacío.

Se respaldaron SQLite, checkpoints, sesión y CSV; luego se incorporaron únicamente
las tres descargas completas mediante JobStore y su reserva/transacción originales.
Sus páginas y el CSV quedaron actualizados. Se comprobó que los 45 BL Guardado
y 83 filas anteriores permanecieron idénticos: ahora son 48 BL y 86 filas,
con 34.805 pendientes. Los intentos históricos se conservan; cada recuperación
añade un intento confirmado, sin reiniciar contadores ni volver a consultar guardados.
El respaldo y diagnósticos son privados bajo `bots/bls/data/`. No hubo descarga
masiva ni modificación de los repositorios o fuentes originales. Se reabrió la app
actualizada en BLs tras un cierre ordenado y sin consultas activas.

Validación: 13 pruebas locales de búsqueda y paginación (incluido GET al perder foco),
cuatro de panel/conexión/reanudación y verificación de integridad de fuentes.
Además, el nuevo parser reconoció la coincidencia exacta de una respuesta GET
real que previamente había terminado en timeout. Este diagnóstico de tres BL
no acredita todos los demás casos posibles del portal.

## Trabajo activo y diagnóstico — 14/10/2026

Los Descargando se ordenan antes de recortar las primeras 200 filas y se muestran
además en «Descargando ahora», con manifiesto, BL, página y filas acumuladas.
Los eventos de reserva/página se envían inmediatamente, incluidos los trabajadores
que cambian a la vez. La página 1 se anuncia antes de esperar la descarga, mientras
el checkpoint sigue en cero hasta validarla. La preparación/espera de conexión
conserva los contadores y publica su mensaje.

Una petición del usuario permitió comprobar aparte el BL interrumpido `26560432`
del manifiesto `1-0-26360645-P036-02/09/26`: obtuvo una fila verificada. No se importó
esa prueba al lote ni se hicieron descargas masivas. La cola operativa conserva
2.641 BL guardados y 4.578 filas. El motivo exacto de la parada anterior no quedó
registrado; no se atribuye a un fallo de TICA ni se anuncia una causa demostrada.
Ahora `batch_worker.py` y `manifest_service.py` registran excepciones completas en
`data/logs/bls.log` y conservan el motivo en el historial. Un error OSError al escribir
el JSON auxiliar durante una notificación no aborta los datos confirmados en SQLite.
Pruebas locales: orden con más de 200 trabajos, reservas simultáneas, JSON bloqueado,
QML activo y reanudación/paginación/búsqueda existentes. Evidencia de la única
consulta real en `runtime/bls_revision/20261014-011605/`.

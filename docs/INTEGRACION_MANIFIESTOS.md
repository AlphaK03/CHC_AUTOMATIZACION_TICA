# Manifiestos y conexión con BLs

Entrega del 13/10/2026. Origen: `D:/PortafolioDesarrollador/Manifiestos_Bot2`,
estado real de sus archivos en disco, incluidos los que no estaban registrados en Git.
El original no se modificó ni se ejecutó. Se copiaron 28 archivos Python de fuentes
y pruebas, más requisitos y documentación de referencia, a `bots/manifiestos/`.
Los hashes de esos 28 archivos están en `source_manifest.json`; sus extractores
permanecen intactos. Los cambios funcionales viven en adaptadores nuevos.

## Objetivo dentro del proyecto

CHC Workbench debe reunir los motores y los generadores de bases en un repositorio,
con interfaz sencilla, procesos independientes y almacenamiento propio. Esta
incorporación añade una familia de procedimientos por manifiesto y permite preparar
y consumir las bases de BLs sin abrir otra aplicación ni mover Excel manualmente.
No sustituye el proveedor de DUAs por régimen usado por los cuatro bots DUA.

## Uso

1. Abrir `Abrir_Workbench.bat` y seleccionar **Manifiestos**.
2. Elegir procedimiento, mes, año y modalidades. El nombre de tabla es opcional.
3. Pulsar **Iniciar consulta**. **Detener** conserva los resultados confirmados.
4. Para continuar un lote, elegirlo en **Ejecuciones guardadas** y volver a iniciar.
5. **Ver resultados** abre su carpeta pública, que contiene exclusivamente CSV de datos.

Cambiar de procedimiento no detiene el anterior. Cada uno mantiene su configuración,
cola, proceso e historial. Las modalidades seleccionadas se recorren secuencialmente,
como en el original; dentro de cada modalidad se aplica su concurrencia.

En **Más → Configuración** se encuentran descargas simultáneas, navegador visible,
espera, intervalo dentro del mes, selección de IDs, límite de manifiestos, Courier
para Conocimientos y carpeta de resultados. Los IDs se separan con espacios y el
límite cero significa todos. Guardar recibe confirmación del proceso, no simula éxito.
Tabla principal representa el listado del período; los filtros de IDs/límite están
destinados a los procedimientos que recorren manifiestos.

El visor muestra hasta 200 trabajos por página y permite buscar por identificador
cuando el procedimiento está detenido. Los detalles de error aparecen en la fila
y en su ayuda al pasar el cursor. **Más → Pendientes y exclusiones** prepara un CSV
de revisión en almacenamiento privado. **Actualizar CSV** no consulta TICA.

## Contratos conservados

| Procedimiento | Contenido y comportamiento |
| --- | --- |
| Tabla principal | Encabezados y texto del listado del portal, sin imponer un esquema artificial. La cantidad visible debe coincidir con la respuesta confirmada. |
| Conocimientos | 15 columnas originales; todos los Courier por defecto; 1–32 descargas, 32 predeterminadas; páginas, offsets, secuencias, anclas de reanudación y EOF originales. |
| DUAs por manifiesto | Índice, diez columnas del portal y `manifiesto`; cuatro descargas predeterminadas; filas repetidas y texto original. |
| Movimientos de manifiesto | Índice, catorce columnas del portal —incluida la columna sin nombre— y `manifiesto`; cuatro descargas predeterminadas. |
| Contenedores | Solo Llenos; manifiesto → contenedor → mercancías; índice y 18 campos originales de negocio; cinco descargas predeterminadas. |

Conocimientos, DUAs y Movimientos utilizan las colas/extractores originales,
manteniendo confirmación transaccional, trabajos vacíos válidos, checkpoints y
exclusiones. DUAs mantiene la excepción `frmAmbiente` para `hcgduama.aspx`, la
reconsideración de antiguas exclusiones por conversión y las reglas de contadores
enmascarados/desbordados. Sus descargas continúan sin timeout total ni HTTP,
hasta respuesta o Detener. DUAs/Movimientos conservan el contexto HTTP independiente
por manifiesto sin compartir `ASP.NET_SessionId`; no se generaliza esto a otros flujos.

Tabla principal y Contenedores tienen persistencia SQLite añadida en `RowsStore`.
Contenedores confirma el manifiesto completo: si falla una mercancía queda pendiente,
sin guardar parcialmente sus otras filas. La respuesta del filtro debe confirmar
el número de contenedores; un cero inicial de la pantalla no acredita vacío.
Se comprueban cantidades y EOF de mercancías cuando el portal los proporciona.
Una paginación no completada permanece pendiente. Una mercancía vacía no se convierte
silenciosamente en éxito. Se evita duplicar `IDManifiesto` al unir contenedor y
mercancías: hay un único campo de identidad, con el valor original.

Los Movimientos de manifiesto son un procedimiento distinto de XMovimientos por
DUA. Los DUAs asociados a manifiestos tampoco equivalen automáticamente al universo
de regímenes de DUAS_SCRAPPING. No cruzarlos ni sustituir proveedores por su nombre.

## Progreso existente

**Más → Importar progreso SQLite** permite copiar una base original de Conocimientos,
DUAs o Movimientos. Se abre en modo de solo lectura y se obtiene una instantánea con
SQLite backup; se verifica integridad y procedimiento antes de usarla. No sustituye
un lote que ya tenga progreso en el Workbench. Se conservan resultados, trabajos,
intentos, exclusiones y páginas parciales. Reanudar adquiere el bloqueo del lote
antes de recuperar reservas interrumpidas. Nunca se infiere éxito del máximo índice CSV.
No se importan automáticamente datos de producción ni se consulta el original al arrancar.

## Crear y usar bases para BLs

En Manifiestos, pulsar **Crear base para BLs**. Elegir año —0 para todos—, mes y
modalidad antes de **Cargar datos**. Se buscan los resultados confirmados de
Conocimientos de este Workbench. **Archivos y opciones** permite añadir CSV, XLSX,
SQLite o carpetas externas, elegir fuentes, preferir SQLite e incluir históricos.
La lectura de fuentes externas no las modifica. Los meses se obtienen de sus filas;
no se presume que un archivo externo contenga solo el período de su nombre.

Elegir meses y fuentes y generar Excel o SQLite. Se conserva el generador original:
Courier=N explícito, identificadores textuales, ceros iniciales, normalización de
secuencia, orden, deduplicación de claves equivalentes y exclusión auditada de BL
conflictivos. Solo se usan filas SQLite confirmadas, no páginas parciales.
Los pendientes se muestran y no se afirma cobertura mensual completa por disponer
de algunos resultados. Detener o un fallo no publica una base a medio generar.
Sustituir un destino existente exige marcarlo explícitamente.

La salida SQLite tiene únicamente la tabla `BLS` con cinco columnas TEXT:
`IDManifiesto`, `Secuencia Tica`, `BL original`, `Fecha Manifiesto`, `Mes`.
Excel mantiene sus hojas BLS/BLS_002/etc. y los valores de texto. La auditoría es privada.
Después de generar, **Abrir base en BLs** selecciona esa entrada y navega al módulo;
la consulta de BLs se inicia únicamente al pulsar su botón Iniciar.

Ampliación: BLs también ofrece **Desde Conocimientos → Elegir meses…**. El proveedor
comprueba que las descargas estén terminadas, ofrece sus meses y modalidades reales
y genera automáticamente la base al iniciar. El generador manual de este apartado
sigue disponible. Leer [la conexión directa](BLS_DESDE_CONOCIMIENTOS.md).

BLs deja de ser demo: su panel QML ejecuta `bots/bls/src/core/engine.py` en un proceso
propio, acepta Excel o SQLite, permite indicar hoja, configurar concurrencia e
intentos, detener, retomar el lote, exportar y revisar pendientes. Se conserva el
modo original de fechas por entrada, los parsers y el contenido de sus resultados.
No es una reproducción de todas las opciones avanzadas de su GUI clásica;
la copia clásica permanece disponible. Cambiar solo el formato de entrada, si
filas/orden/hoja coinciden, conserva la identidad del lote del motor original.

**Más → Dividir CSV para Excel** divide por streaming, con cabecera y límite de
1.048.576 filas por parte. Las partes se guardan aparte en la zona de herramientas.

## Arquitectura, rutas e instalación

- GUI: `workbench/batch_bridge.py`, `qml/ManifiestosPage.qml` y `ManifiestosBaseDialog.qml`.
- Protocolo/proceso: `chc_runtime/batch_worker.py`; un worker por procedimiento,
  otro para crear bases y otro independiente para BLs. Solo se conectan cuando hacen falta.
- Adaptación: `chc_runtime/manifest_service.py` y `manifest_adapters.py`.
- Estado/configuración/historial: `bots/<módulo>/data/workbench/<procedimiento>/session.json`.
- Progreso: `bots/<módulo>/data/jobs/<procedimiento>/<id interno>/.../SQLite/`.
- Salida pública: `bots/<módulo>/resultados/<nombre elegido>/<archivo de datos>.csv`.
- Bases BLs: `bots/manifiestos/bases_bls/`; auditoría bajo `data/bases_bls/auditoria/`.
- Logs, revisiones, propietarios de publicaciones y partes CSV permanecen en `data/`.

Los identificadores internos nunca se usan como nombre visible de carpeta de resultados.
Un CSV ajeno o un destino perteneciente a otro lote se conserva y se solicita otro
nombre de tabla. Un CSV bloqueado conserva la versión pública anterior; SQLite
retiene los datos nuevos y se puede volver a exportar.

En un equipo nuevo: Python 3.12, `Instalar_Workbench.bat`, `Instalar_Manifiestos.bat`
y `Instalar_BLs.bat`, además de los instaladores de los cuatro módulos DUA si se usan.
Cada módulo tiene su entorno propio y lock de paquetes. No utiliza el entorno original.
`bots/manifiestos/run_bot.py` permite abrir explícitamente la copia clásica con
configuración propia mínima; no se lanza desde la operación normal del Workbench.

## Una instancia

`workbench/single_instance.py` combina `QLockFile` y `QLocalServer` por usuario.
Una segunda apertura envía activación y termina antes de crear workers. Se restaura
y enfoca la ventana existente. Los bloqueos abandonados se gestionan con Qt.
Al actualizar desde una versión antigua, se reconoce su ventana y se activa sin
interrumpir consultas. No se cierran a la fuerza ventanas antiguas activas.
`--capture` y `--smoke-test` son comprobaciones sin ventana interactiva y quedan aisladas.

Se mantienen protección Windows de procesos hijos y cierre acotado. El EOF del padre
solicita detener; si no puede finalizar, el siguiente inicio recupera las reservas
bajo su bloqueo. NumPy y extensiones nativas se cargan en el hilo principal del
worker antes de leer stdin: evita el bloqueo de inicialización observado en Windows.
El protocolo es UTF-8 explícito, independiente de la página de códigos del equipo.

## Verificación y límites reales

Comprobaciones enfocadas, con almacenamiento temporal y sin nuevas consultas a TICA:

- Cinco procedimientos, formulario Playwright y servidor HTTP local: CSV/SQLite,
  múltiples páginas de Conocimientos, vacíos válidos, esquemas inválidos,
  exclusión de DUAs, reanudación sin repetir guardados y Contenedores sin parciales.
- Base SQLite desde Conocimientos → lector/motor BLs → resultados, preservando
  un BL de 23 dígitos con ceros. Sustitución sin confirmar rechazada.
- Importación de progreso conservando el SHA-256 del SQLite de origen.
- Detener con consultas activas conserva guardados y deja cero reservas en curso.
- CSV externo preexistente conservado antes de iniciar descargas.
- Botones QML reales: Iniciar → Cargar datos → Generar base → Abrir en BLs → Iniciar.
- Segunda apertura desde otro proceso activa la ventana primera y libera el bloqueo al cerrar.
- Smoke de seis vistas y captura sin advertencias QML; 166 hashes de copia verificados
  —138 de la línea base anterior y 28 de Manifiestos—. Los originales no se alteraron.

Pruebas: `test_manifiestos_bridge.py`, `test_manifiestos_qml.py` y
`test_single_instance.py` en `workbench/tests/`. No se declara una nueva validación
real del portal: las reglas de extracción se basan en la copia original y en las
comprobaciones locales anteriores. Conviene comenzar el uso con un período o
selección de manifiestos acotados y revisar sus resultados antes de un lote grande.

Este módulo admite operación mensual y fechas dentro de ese mes. No implementa aún
el calendario diario continuo ni la espera de las 00:01 para Manifiestos/BLs;
esa automatización sigue siendo una etapa posterior. Los cuatro bots DUA conservan
sus calendarios y automatización existentes, sin cambios en sus motores.

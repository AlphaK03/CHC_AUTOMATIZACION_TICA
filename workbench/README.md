# CHC Workbench

Aplicación de escritorio con Python, PySide6 y Qt Quick/QML. Detalles, DUAs
Tránsito, Talón y XMovimientos están integrados con procesos propios y soporte
común en `chc_runtime/`. BLs y Manifiestos también tienen motores integrados.
Una segunda apertura activa la ventana existente, sin iniciar otros motores.
La visión completa está en el [README principal](../README.md) y en el
[contexto para futuras sesiones](../docs/CONTEXTO_PROYECTO.md).

## Abrir

Desde la raíz del repositorio, hacer doble clic en `Abrir_Workbench.bat`.
Abre directamente Detalles con dos pestañas: Procesamiento y Configuración.
Base de datos abre una ventana aparte; las acciones secundarias están en Más.
El entorno local está preparado. En un equipo nuevo, ejecutar primero
`Instalar_Workbench.bat` y los instaladores de los módulos que se utilizarán
(Python 3.12); la lista completa está en el README principal.

Alternativa en PowerShell:

```powershell
py -3.12 -m venv workbench/.venv
.\workbench\.venv\Scripts\python.exe -m pip install -r workbench/requirements.txt
.\workbench\.venv\Scripts\python.exe workbench/app.py
```

Se instala `PySide6-Essentials==6.12.0`, con los bindings y módulos Qt necesarios.
La conexión opcional a SharePoint usa MSAL, msal-extensions y requests en este
mismo entorno. El panel no usa WebEngine ni un servidor web. Las dependencias del motor de
Detalles se instalan por separado en `bots/detalles/.venv/`.

## Eliminación de bases

En Detalles, Tránsito, Talón y XMovimientos, abrir **Base de datos**, seleccionar
la tabla y elegir **Eliminar tabla**. Eliminar filas o limpiar completados usa
la misma confirmación. Escribir exactamente **BORRAR**, en mayúsculas y sin
espacios; el botón permanece deshabilitado con cualquier otro texto. El diálogo
siempre muestra la tabla elegida y limpia el campo al volver a abrirlo.

En Manifiestos, elegir primero el procedimiento y su ejecución guardada; en BLs,
elegir la ejecución. Abrir **Más → Eliminar base de datos…**. Retira esa ejecución
con todas sus modalidades, pendientes, resultados internos y checkpoints. Conserva
los CSV exportados, las bases de entrada, las instantáneas preparadas para BLs y
las copias online. No elimina otro procedimiento ni hace consultas a TICA.

No se permite borrar durante una consulta ni mientras una revisión visible está
usando el lote BLs/Manifiestos. Si cambió la selección, hay un bloqueo de otro
escritor o la ruta no es una carpeta propia del lote, la operación se rechaza.
La palabra también se valida en el worker, no solo en el botón.

Los cuatro DUA conservan sus respaldos SQLite en `data/queues/backups/`.
Manifiestos y BLs trasladan los archivos internos a
`bots/<bot>/data/deleted/<procedimiento>/<operación>/files/`, acompañados por
`deletion.json` con el registro original. La ruta aparece en el estado y el log.
Los archivos `.lock` permanecen en su ubicación. El respaldo no se ofrece como
fuente para BLs ni cuenta como progreso mensual. Si el traslado falla o la app
se cierra antes de confirmar el catálogo, se revierte; un recibo por operación
evita restaurar un borrado confirmado aunque se recree la misma ejecución.

La recuperación de un borrado confirmado es manual; todavía no hay botón
Restaurar. Volver a iniciar una ejecución eliminada crea progreso nuevo y mantiene
las protecciones existentes frente a conflictos con CSV anteriores.

## Detalles operativo

Seleccionar **Detalles** en el panel lateral. Permite importar Excel, conservar
tablas SQLite, consultar y retomar pendientes, detener, exportar CSV/TXT/JSON,
buscar e inspeccionar resultados, administrar filas y configurar el motor.
La tabla **Validación · 2 DUAs originales** contiene resultados de la prueba real
de esta entrega. Seleccionarla y abrir **Base de datos** para revisar sus campos.

El [manual de integración](../docs/INTEGRACION_DETALLES.md) documenta cada función,
los respaldos, las rutas propias y el acceso temporal a la interfaz clásica.
Consultar resultados guardados y exportarlos no realiza consultas a TICA.

Mientras el motor guarda, una lectura de la lista puede encontrar la base ocupada.
La actualización automática conserva las filas y su posición, y vuelve a intentar
en el siguiente refresco. Ese bloqueo temporal de lectura no detiene las consultas
ni se presenta como fallo del motor. Los errores reales de extracción o escritura
siguen visibles. Un error de lectura se limpia cuando la lista vuelve a cargar.

Tras un cierre inesperado, SQLite puede necesitar deshacer una transacción sin
confirmar antes de permitir la lectura. Al cargar cualquiera de los cuatro bots
DUA, el módulo recupera ese caso con el lote libre y un respaldo previo de la
base y su journal en `bots/<id>/data/queues/backups/rollback-*`. No borrar el
archivo `-journal`: contiene la información para recuperar los datos confirmados.
El panel conserva éxitos, intentos y reservas; retomar las consultas sigue siendo
una acción explícita. La recuperación queda registrada en Actividad y en el log.

Esta rama añade **Diario automático** en Modo: indicar Desde, pulsar Iniciar
automático y revisar Calendario. No requiere Excel y conserva Manual. En un
equipo nuevo ejecutar `Instalar_Base_Diaria.bat`. [Uso y límites](../docs/PILOTO_DETALLES_DIARIO.md).
`--daily` abre esa vista sin iniciar descargas.

Al reabrir la app basta pulsar **Iniciar automático**: retoma el primer día por
atender y omite los días completados o ya omitidos del automático. Desde, Hasta
y la selección del Calendario muestran el rango que queda, sin perder el origen
guardado ni los huecos intermedios. Un rango elegido sirve para retomar; al acabarlo
continúa hasta el último día disponible y espera a las **00:01 de Costa Rica**.
Cuando llega esa hora incorpora el nuevo día, incluso al cambiar de mes.
La apertura de la app por sí sola no inicia consultas. Los reintentos explícitos
de día/mes y el inicio conjunto por mes siguen limitados a su período.

## DUAs Tránsito operativo

Seleccionar **DUAs Tránsito** en la barra lateral. Usa la misma interfaz, tablas,
calendario, configuración y recuperación que Detalles, con almacenamiento propio.
Manual acepta `Total_DUAS - Transito.xlsx`; Diario automático descarga solo TRANSITO.
Su CSV conserva ocho columnas y todas las líneas de cada DUA. El visor permite
elegir la línea. [Funciones, compatibilidad y límites](../docs/INTEGRACION_TRANSITO.md).

## Talón y XMovimientos

Seleccionar el bot en la barra lateral. Manual admite la misma base
`Total_DUAS - Importacion.xlsx`; Diario automático obtiene los cuatro regímenes
de importación y reutiliza la base verificada entre ambos bots. Cada uno conserva
sus tablas, calendario, reintentos y resultados. Talón exporta siete columnas
por tributo; XMovimientos, seis por movimiento con los bultos agrupados y sumados.
El visor permite seleccionar cada fila. Instalar con `Instalar_Talon.bat` o
`Instalar_XMovimientos.bat`, más el proveedor para bases automáticas.
[Uso, formato, compatibilidad y evidencia](../docs/INTEGRACION_IMPORTACION.md).

## Manifiestos y BLs

En los cinco procedimientos de Manifiestos, la columna **Modalidad** identifica
cada resultado como **Marítimo**, **Aéreo** o **Terrestre**. El listado principal
muestra una fila `listado` por modalidad: sus filas e intentos pertenecen solo
a esa descarga. Antes ambas compartían la clave de la vista y una podía ocultar
a la otra; las bases y los CSV permanecían separados.

El resumen general suma todas las modalidades guardadas. Debajo aparecen sus
conteos independientes de guardados, pendientes, en curso, excluidos y filas.
El filtro **Todas / Marítimo / Aéreo / Terrestre**, junto a Buscar, cambia las
filas visibles; los contadores siguen mostrando la cobertura completa del lote.
Buscar y paginar respetan esa modalidad. Los trabajos activos se muestran
aparte con su modalidad, incluso si el historial está filtrado a otra.

**TICA** abre la base/modalidad exacta de la fila elegida. También funciona con
dos filas llamadas `listado`; no requiere reconsultar ni migrar las descargas
ya guardadas. Cambiar el filtro no modifica la configuración aún sin guardar.

En **Manifiestos**, la barra horizontal permite elegir **Manifiestos**,
**Conocimientos**, **DUAs**, **Movimientos** o **Contenedores**, con el mismo estilo
de la barra lateral. En **Procesamiento**, elegir período y modalidad y pulsar
**Iniciar consulta**. Cada procedimiento conserva su historial y funciona
independientemente; cambiar de acceso no detiene sus consultas.
El campo **Tabla** es automático y no editable: Octubre 2026 → `octubre26`,
Enero 2027 → `enero27`. Las consultas sin IDs ni límite acumulan por procedimiento,
mes y filtro Courier. Ampliar fechas o pasar de ambas modalidades a una sola
retoma esa misma ejecución; consulta el listado vigente, agrega manifiestos nuevos
y procesa los pendientes del rango seleccionado sin repetir los guardados.
Los lotes anteriores conservan nombre, rutas y progreso; no se fusionan bases
históricas independientes. Las selecciones por IDs/límite siguen aisladas y
conservan sus sufijos y su lista fija. Courier distinto también tiene un acumulado propio.
Los cinco procedimientos conservan CSV propios dentro de la carpeta del período;
sus tablas y progreso siguen separados. BLs conserva su nombre manual o el generado
desde Conocimientos porque su base puede reunir varios períodos.
**Configuración** reúne los parámetros de consulta y la carpeta de resultados;
los filtros de fechas, IDs, límite y Courier están en **Opciones avanzadas**.
Importación de progreso SQLite y herramientas siguen en **Más**.

Ejemplo: consultar octubre del 1 al 17 con Marítimo y Aéreo; en noviembre ampliar
al 31 e iniciar de nuevo. Se conservan los resultados de ambas modalidades y se
añaden los manifiestos que aparecieron después. Si se elige solo Marítimo, solo
se actualiza esa modalidad; Aéreo mantiene su avance. Cada CSV público contiene
el acumulado del mes de su modalidad, también al consultar un rango más pequeño.
Un inicio nuevo vuelve a leer el listado para descubrir novedades; no es un
calendario automático. La unidad guardada sigue siendo el manifiesto: no vuelve
a extraer sus detalles ya confirmados para buscar cambios internos posteriores.

La primera actualización de una base anterior crea respaldo SQLite bajo
`bots/manifiestos/data/backups/`. Rangos, selección confirmada y finalización se
registran en SQLite; ni el nombre mensual ni el último rango elegido prueban
cobertura completa. BLs recibe solo rangos terminados y verificados. Su motor,
firmas de entrada y checkpoints no cambian con esta actualización de Manifiestos.
**Ver resultados** abre únicamente sus CSV de datos. BLs también ofrece
Procesamiento y Configuración. Las páginas permiten desplazarse en ventanas pequeñas.

Capturas con almacenamiento aislado: [barra horizontal](../docs/preview/manifiestos-horizontal.png)
y [configuración](../docs/preview/manifiestos-configuracion.png).

**Crear base para BLs** permite cargar meses de Conocimientos, seleccionar fuentes
y generar SQLite o Excel Courier=N. **Abrir base en BLs** prepara la entrada del bot;
las consultas empiezan al pulsar Iniciar. También se admiten entradas externas.

En **BLs → Desde Conocimientos**, **Elegir meses…** ofrece solamente descargas
terminadas de Marítimo/Aéreo. **Iniciar consulta** genera la base y ejecuta BLs.
No hay que elegir un archivo intermedio. Los rangos indican sus días disponibles.
[Uso, disponibilidad y recuperación](../docs/BLS_DESDE_CONOCIMIENTOS.md).

La lista BLs muestra **Fila** y **Manifiesto / BL original**, incluidos sus ceros,
al consultar y al recuperar SQLite. Buscar BL también encuentra el manifiesto.
**Continuar pendientes** aparece al retomar la misma selección con pendientes.
Durante la preparación se conservan los contadores guardados; al consultar, las
filas en curso aparecen primero y sus eventos actualizan la misma fila.
**Página** indica la página solicitada durante la descarga, o la última guardada
al detener; su ayuda muestra la última página verificada. **Filas** muestra lo
acumulado por BL. Esas filas parciales se conservan para continuar, pero el
contador general de **filas confirmadas** incluye únicamente BL completos.
Al pulsar Continuar pendientes se verifican la primera y última páginas guardadas
y se continúa con la siguiente. Si cambiaron, el BL queda pendiente para revisión.
Los lotes anteriores conservan sus resultados; muestran «—» en Página cuando no
hay historial por páginas. No se inicia una consulta automáticamente al abrir.
[Captura con datos de prueba](../docs/preview/bls-paginas.png).

Un timeout indica que no se pudo confirmar la respuesta, no que el BL esté vacío
o ausente. El bot acepta tanto la respuesta de Confirmar como el refresco GET
de TICA, comprobando fechas, manifiesto, BL, secuencia y columnas. Si no puede
validarlas, conserva las páginas y deja el BL pendiente con el motivo del fallo.

Instalación nueva: `Instalar_Manifiestos.bat` e `Instalar_BLs.bat`.
[Contratos, recuperación, rutas y alcance comprobado](../docs/INTEGRACION_MANIFIESTOS.md).

## Inicio conjunto por mes

En **Vista general → Iniciar bots por mes → Elegir bots…**:

1. Elegir mes y año. Se ofrece inicialmente el último mes terminado; meses actuales
   o futuros no se inician como descargas completas.
2. Marcar los procesos deseados, o usar **Marcar todos** y desmarcar excepciones.
   Manifiestos muestra sus cinco procedimientos por separado para elegirlos
   individualmente y asignarles sus propios trabajadores.
3. Ajustar los números de trabajadores: hasta 20 para cada DUA y BLs, hasta 32 para
   Conocimientos/DUAs/Movimientos/Contenedores. Tabla usa un trabajador para el listado.
   Se muestran las cantidades guardadas de los módulos y el total elegido.
4. Elegir modalidades de Manifiestos/BLs. Terrestre corresponde solo a Manifiestos;
   BLs utiliza Marítimo/Aéreo y exige todas las modalidades elegidas completas.
5. Pulsar **Iniciar seleccionados**. Cada fila informa preparación, consultas,
   finalización, pendientes, bloqueos u operación ya ocupada.

Los cuatro bots DUA reutilizan el calendario existente con Desde=1 y Hasta=último
día del mes, descargan sus bases propias y acumulan resultados en su tabla mensual.
El rango termina al completarse; no queda esperando el siguiente mes. Se exige
confirmación de configuración para la petición exacta antes de iniciar, y se
comprueba que fechas/trabajadores no hayan cambiado. Si no había carpeta elegida,
se usa la carpeta madre común `RESULTADOS/` (o el directorio aislado correspondiente).

Manifiestos envía el mes completo al worker de cada procedimiento, sin cambiar
la vista abierta. Limpia únicamente en esa nueva petición los filtros de días,
IDs, límite y Courier que pudieran quedar de otra selección; mantiene otras
preferencias y su carpeta. Los lotes filtrados anteriores quedan intactos.

BLs utiliza **Desde Conocimientos** para el mes/modalidades exactos. Si se marca
Conocimientos, espera su finalización verificada antes de preparar la base.
También puede esperar una ejecución existente del mismo mes completo y modalidades,
sin modificarla. Con pendientes, exclusiones, errores o detención no inicia BLs.
Si solo se marca BLs, comprueba primero que su base mensual ya esté disponible;
no utiliza una entrada manual vieja ni un rango parcial. La publicación y la
recuperación siguen usando las protecciones y firmas originales.

Un proceso ocupado se omite, conservando su trabajo, período y configuración.
**Detener este inicio** cancela preparaciones/esperas y solicita detener únicamente
los procesos iniciados por esta acción; conserva avances y no detiene ejecuciones
ajenas observadas. Detener desde el panel del bot también cancela su continuación
pendiente. Las respuestas tardías no pueden iniciar tareas después de cancelar.
Al cerrar, se cancelan continuaciones; al abrir no arranca ningún mes automáticamente.
Las selecciones del formulario se conservan al navegar durante la sesión; para
retomar después de cerrar hay que elegir de nuevo y pulsar Iniciar seleccionados.

Implementación en `month_launcher.py`; pruebas con procesos originales, fuentes y
portales locales en carpetas temporales, sin TICA. [Vista oscura](../docs/preview/inicio-mensual.png)
y [vista clara](../docs/preview/inicio-mensual-claro.png).

## Bitácora mensual

**Vista general → Bitácora de descargas** reúne los meses identificados en el
historial real, del más reciente al más antiguo. Cada mes muestra Detalles,
Tránsito, Talón, XMovimientos, BLs y Manifiestos. Junto al nombre de cada bot se
muestra **16/31**, solo números, en blanco y negrita de tamaño mediano: días
completos respecto a los días del mes, incluidos los aceptados manualmente.
En Manifiestos se cuentan las fechas cubiertas por los cinco procedimientos y
las modalidades de cada uno; no se suman rangos distintos como días comunes.
**Completado** acredita cobertura
mensual y resultados según la política de cada bot. En la comprobación automática,
Detalles exige todos sus DUAs guardados. Los demás admiten omitidos fuera del resultado final; sus pendientes
se conservan y pueden reintentarse. Vacíos verificados de XMovimientos cuentan aparte.
**En curso**, **Parcial**, **Pendiente** y **Sin iniciar** permiten ver qué falta.
**Lote listo** significa que terminó la selección, pero no se acredita todo el mes.
**Al día** indica que el mes actual está terminado hasta la última fecha consultable,
respetando las 00:01 de Costa Rica; al aparecer un nuevo día vuelve a comprobarse.
Una fuente ilegible queda **Sin verificar**.

**Cierre manual…** permite elegir bot/procedimiento y **Marcar completo**, o
**Usar comprobación automática** para retirar esa marca. No modifica resultados
ni borra pendientes. Aplica a todos los bots, incluido Detalles, y a los cinco
procedimientos de Manifiestos. La marca aparece como **Completado manual**, permite
**Subir a SharePoint** y se invalida al cambiar datos o intentos.

Los días aceptados mediante **Calendario → Marcar completado** cuentan también
en la bitácora: el detalle muestra días completos, verificados y manuales por
separado. Cuando todos los días del mes están cubiertos, el bot aparece como
**Completado manual**; en el mes actual, **Al día (manual)** hasta la última fecha
consultable. Los días todavía no disponibles no se dan por completos. Estas
marcas persisten durante los reintentos; se retiran con **Quitar marca manual**
en el calendario. Quitar un cierre mensual conserva las marcas de los días.

Pasa sobre un estado para ver cantidades, cobertura y modalidades. Pulsarlo abre
el bot; no inicia ni cambia su selección. **Ver procedimientos de Manifiestos**
despliega Manifiestos, Conocimientos, DUAs, Movimientos y Contenedores. El contador
«1/5 completos» se refiere a esos procedimientos; un modo terminado no oculta
otra modalidad pendiente. El mes puede mostrar bots todavía sin descargas.

La lectura se ejecuta en un hilo, sin bloquear la ventana ni importar motores.
Se actualiza al entrar, con **Actualizar**, cada 30 segundos y con eventos de
progreso agrupados a intervalos de 10 segundos. Usa únicamente SQLite/JSON
existentes en modo lectura; no modifica su progreso ni realiza consultas a TICA.
Solo el cierre manual guarda metadatos separados en
`runtime/workbench/monthly_overrides.json`. Así conserva el historial entre aperturas y refleja cambios o eliminaciones
del catálogo. Las demostraciones no se presentan como descargas reales.

Los cuatro bots DUA verifican sus días del calendario contra sus resultados
guardados. Una tabla manual se asocia por nombre/hoja mensual (`septiembre26`,
`Septiembre 2026`), pero ese nombre no prueba cobertura: solo puede mostrar
Lote listo hasta contar con días verificados. Tablas sin mes identificable no
se asignan por su fecha de creación. BLs agrupa por el Mes original de cada trabajo,
incluso en bases de varios meses; la cobertura procede de la base de Conocimientos.
Manifiestos comprueba selección, resultado confirmado, finalización y ausencia de
páginas parciales en los trabajos que cuentan para el cierre. Conserva páginas de
los omitidos para reintento y reúne rangos completos de una misma modalidad; filtros de
IDs/límite/Courier no acreditan el mes entero.

[Vista oscura con datos aislados](../docs/preview/bitacora-mensual.png) y
[vista clara](../docs/preview/bitacora-mensual-claro.png).

## Interfaz y demostraciones

Los paneles de **Actividad** de Detalles, Tránsito, Talón y XMovimientos conservan
la fila y su desplazamiento al bajar a leer mensajes anteriores, aunque lleguen
logs o cambien los contadores. Solo siguen las novedades si estás al inicio;
volver arriba restablece ese seguimiento. Arrastrar la barra o desplazar la lista
interrumpe un seguimiento pendiente. **Limpiar vista** mantiene su comportamiento.
La lista es incremental, con los mismos 2.000 mensajes por bot; al salir los más
antiguos, permanece cerca del final en lugar de saltar arriba. Las seis vistas de
demo usan el mismo componente, con su límite previo de 30 eventos y altura fija.
BLs y Manifiestos reales conservan sus estados/listas de trabajos actuales;
esta corrección no añade ni modifica consultas de esos motores.

- Navegación lateral expandible y contraíble, con iconos y ayudas.
- Vista general y acceso independiente a seis módulos; Manifiestos agrupa cinco procedimientos.
- Búsqueda por nombre o descripción y estado de búsqueda vacía.
- Temas oscuro y claro, transiciones y componentes reutilizables.
- Base sintética de 240 registros por módulo de demo: **Cargar base de ejemplo**.
- Inicio, pausa, continuación y reinicio de simulaciones independientes.
- Uno a cuatro trabajadores para cambiar el avance de la demo.
- Progreso, resultados de muestra y actividad por módulo y por sesión.
- Cambio de página sin perder la simulación de otro módulo.
- Diálogos de contexto e integraciones futuras.

`Ctrl+K`: buscar. `Ctrl+B`: contraer/expandir la barra. `Escape`: limpiar búsqueda.
El tema se guarda entre aperturas en `runtime/workbench/preferences.json`.

La interfaz toma la clásica como referencia: tabla, carpeta, progreso, actividad
y ejecución. Las opciones técnicas están plegadas en Configuración. Para cambios
visuales basta una comprobación breve; las suites completas se reservan para
cambios sensibles del motor, almacenamiento o recuperación.

**Exportar demo** muestra un aviso, no escribe archivos. Las bases, resultados y
eventos de las demos viven en memoria y se descartan al cerrar. `DEMO-0001`, etc.,
no son DUAs. Usar `--demo` para abrir también Detalles en modo de demostración.

## Responsabilidades

XMovimientos presenta **Vacío** como resultado de una consulta sin movimientos,
con contador separado de los guardados y de los pendientes. En **Base de datos**
se puede filtrar Vacías/Errores/Vacías por verificar. **Reintentar vacíos** consulta
los vacíos seleccionados; sin selección, consulta todos, incluidos los pendientes
de verificación. No vuelve a descargar los guardados. Se conserva el historial y
la fecha de la última consulta vacía en **Ver**. Los vacíos confirmados permiten
continuar al siguiente día y no añaden registros al CSV. Esto aplica a XMovimientos;
Talón conserva su tratamiento anterior de tributos ausentes.

Los DUAs en curso se mantienen arriba de Actividad; los BL/manifiestos activos
aparecen en **Descargando ahora**, antes del listado. BLs muestra página solicitada
y filas acumuladas en checkpoints; siguen siendo parciales hasta terminar el BL.
El historial de Actividad conserva el desplazamiento manual. Los errores de BLs
se registran también en `bots/bls/data/logs/bls.log`, con su causa; un bloqueo del
historial JSON auxiliar durante el progreso no aborta las consultas de SQLite.

| Archivo/carpeta | Función |
| --- | --- |
| `app.py` | Arranque Qt, carga QML y comprobaciones |
| `demo.py` | Estado sintético por módulo; simulación con QTimer |
| `details_bridge.py` | Proceso aislado de Detalles, comandos y eventos JSONL |
| `preferences.py` | Persistencia del tema |
| `modules.json` | Registro modular y metadatos del adaptador de Detalles |
| `qml/Main.qml` | Ventana, navegación, búsqueda, temas y avisos |
| `qml/Dashboard.qml` | Resumen y tarjetas |
| `qml/BotPage.qml` | Espacio de demostración por módulo |
| `qml/DetallesPage.qml` | Consultas, datos y configuración reales de Detalles |
| `qml/components/` | Tema, iconos vectoriales, botones y paneles |

El proceso Qt no importa los paquetes de los bots. `DetailsBridge` inicia el
worker de la copia con su entorno propio, SQLite, configuración y salida locales.
Cerrar la ventana solicita detener y espera el cierre ordenado del worker.
La interfaz sigue el
[modelo Qt Quick de Qt for Python](https://doc.qt.io/qtforpython-6/tutorials/basictutorial/qml.html).

## Comprobaciones

```powershell
.\workbench\.venv\Scripts\python.exe workbench/app.py --smoke-test
.\workbench\.venv\Scripts\python.exe workbench/app.py --demo --capture docs/preview/workbench-dark.png
.\workbench\.venv\Scripts\python.exe workbench/app.py --demo --page detalles --sample --capture docs/preview/workbench-detalles.png
.\workbench\.venv\Scripts\python.exe workbench/app.py --demo --collapsed --light --capture docs/preview/workbench-light.png
.\workbench\.venv\Scripts\python.exe workbench/app.py --page detalles --capture docs/preview/detalles-integrado.png
py -3.12 tools/verify_import.py --check-sources
```

El smoke test carga QML, recorre seis vistas y comprueba simulación, pausa,
estado conservado al cambiar de módulo, reinicio, búsqueda, barra contraída y
tema; también confirma la finalización de un lote sintético y que no se hayan
importado fuentes de bots. Los modos de comprobación/captura usan offscreen y renderizado software;
terminan automáticamente. En Windows registran fuentes del sistema para capturas.

La comprobación de importación verifica que las fuentes de los bots sigan intactas.
Las capturas están en `docs/preview/`.

## Revisión en TICA y recuperación de pendientes

En la lista de casos, incluidos los guardados, **TICA / Abrir en TICA** abre una ventana
automatizada independiente del proceso de descarga. Funciona también mientras
el bot trabaja. Consulta el identificador seleccionado mediante el formulario
original y deja la primera página visible, incluso ante un error, para revisarla.
Comprueba las filas de la página visible, sin incorporarlas a la base ni al CSV.
No guarda resultados ni modifica colas, progreso o configuración. **Cerrar
revisión** cierra únicamente esa ventana. Disponible para los cuatro bots de DUA,
BLs y las consultas de Manifiestos.

En el calendario diario de Detalles, Tránsito, Talón y XMovimientos, los pendientes
tienen un presupuesto persistente de tres intentos automáticos. Cuando se agota,
el día queda **Omitido**, continúa el siguiente y no se reactiva al reiniciar.
El filtro **Omitidas del automático** permite localizarlos. En Detalles siguen
impidiendo el cierre automático del mes. Los demás bots pueden completar el mes
con esas excepciones fuera del resultado final; una base omitida se distingue de
una base todavía pendiente. Detener una descarga no consume una oportunidad.

**Reintentar mes** y **Reintentar día** solicitan expresamente hasta tres nuevos
intentos por pendiente del período, saltando los resultados ya guardados y sin
cambiar la configuración del rango habitual. El botón del lote usa el mes de la
tabla seleccionada; el del calendario usa el mes mostrado. El mes actual llega
hasta ayer. Esta política aplica al modo diario; la configuración de rondas del
modo Manual permanece independiente.

Para dar un día por revisado bajo tu criterio, seleccionarlo en **Calendario** y
pulsar **Marcar completado**. Aparece en verde como **Completado manual**, junto
al estado del bot y las cantidades reales. **Quitar marca manual** devuelve su
color automático. Disponible para Detalles, Tránsito, Talón y XMovimientos,
incluso mientras otro día se está procesando; cada bot conserva sus propias marcas.

La marca persiste al reabrir y después de los reintentos. Cuenta para completar
el mes en Vista general y habilitar su subida a SharePoint. No cambia los
pendientes, resultados, intentos, bases ni la selección del diario.
**Reintentar mes/día** vuelve a consultar los pendientes aunque el día esté verde;
el diario normal conserva su avance. Las consultas en curso siguen apareciendo
**En curso**; la aceptación manual no simula filas guardadas ni vacíos verificados.
Las marcas se guardan en `bots/<id>/data/daily/manual_completed_days.json`, mediante
reemplazo atómico, fuera de las bases SQLite del motor. La bitácora las distingue
de la cobertura verificada automáticamente y se actualiza al cambiar la marca.
BLs y Manifiestos usan **Vista general → Cierre manual…** por bot/procedimiento,
pues sus motores no disponen del calendario diario DUA.

## Cuenta y SharePoint

La barra lateral ofrece **Cuenta y SharePoint**: conexión opcional con CHC,
una carpeta madre local y una carpeta madre online para todos los bots. El selector
recorre sitios, bibliotecas y carpetas. Cada bot organiza sus CSV por mes; los
nombres públicos están en mayúsculas e incluyen modo donde corresponde.
**Subir a SharePoint** envía solamente CSV de bots con ese mes completo, al día
o cerrado manualmente, mediante una acción explícita. Los días aceptados por el
usuario cuentan para ese cierre en los cuatro bots DUA, incluido Detalles;
BLs y Manifiestos también admiten el cierre manual del mes. **Cierre manual…**
en la bitácora permite cerrar/reabrir la comprobación, sin alterar progreso ni
borrar pendientes. Guardar o exportar no inicia subidas. Los bots
y sus archivos locales siguen funcionando sin sesión o red. **Reintentar envíos**
recupera publicaciones fallidas sin consultar TICA. El registro usa OAuth2/PKCE y
el registro existente **OAuth2 par CHC REPORTES**, con `Sites.Read.All` y
`Files.ReadWrite.All` delegados para explorar y guardar con los permisos de la
cuenta; no utiliza secretos ni los otros permisos del registro.
[Registro, autorización de sitios, límites y pruebas](../docs/SHAREPOINT.md).

Actualizar el entorno con `Instalar_Workbench.bat`. Pruebas independientes:

```powershell
.\workbench\.venv\Scripts\python.exe -m unittest discover -s chc_cloud/tests -v
.\workbench\.venv\Scripts\python.exe -m unittest discover -s workbench/tests -p test_sharepoint.py -v
```

## Pendientes de empaquetado

Los seis motores ya están integrados. Falta preparar y validar una distribución
ejecutable en un equipo limpio, ampliar las variantes reales comprobadas y
completar los generadores/separadores todavía externos. El calendario diario
continuo de BLs es distinto de su inicio mensual ya disponible y sigue pendiente.
El estado y la visión completa están en `docs/CONTEXTO_PROYECTO.md`.

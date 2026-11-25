# SharePoint

La conexión es opcional. **SharePoint**, en la barra lateral, conecta una
cuenta CHC, explora sitios/bibliotecas/carpetas y elige una sola carpeta madre
para todos los bots. También permite elegir una carpeta madre local común.
Los envíos se inician con **Subir a SharePoint** para un mes listo en la bitácora,
**Subir este CSV** para un archivo individual revisado, o un reintento explícito.
Guardar, exportar, conectar, elegir un archivo o abrir la app no inicia subidas.
SQLite, resultados y recuperación permanecen locales. La app funciona sin cuenta o red.

## Registro vigente: OAuth2 par CHC REPORTES

Por indicación del usuario se reutiliza el registro existente:

| Campo | Valor |
| --- | --- |
| Id. de aplicación | `077e19a4-ab53-4e55-8286-ec02dc3cf36c` |
| Directorio CHC | `f7015bc9-c229-413a-ab08-e1e5a76a09f1` |
| Lectura/exploración | `Sites.Read.All`, delegado |
| Archivos de resultados | `Files.ReadWrite.All`, delegado |
| Perfil y foto del usuario | `User.Read`, delegado, autorizado por el usuario el 18/10 |
| Retornos de escritorio existentes | `http://localhost:62190/` y `http://localhost:5000` |

Estos permisos y retornos ya existían. No se modificó ese registro. Se verificó
OAuth real desde MSAL y acceso Graph con la cuenta del usuario. Workbench solicita
solo los tres ámbitos indicados, sin usar `.default`; los otros permisos del
registro (correo, Power BI y SharePoint) no se solicitan para esta integración.
No usa secretos, certificados ni credenciales de aplicación.

El 18/10 se revisó en el Edge abierto **Permisos de API** del mismo appId.
Hay 17 permisos configurados (8 Graph, 2 Power BI y 7 SharePoint); User.Read
aparece concedido para CHC Consultores. El usuario autorizó aprovecharlo para
su perfil/foto. No se agregaron permisos ni se concedió consentimiento desde
Entra: se añadió User.Read a la solicitud OAuth del Workbench. Las filas de
Files/Sites no mostraban consentimiento para todo el inquilino; esto no descarta
consentimiento delegado individual, ya utilizado en las comprobaciones anteriores.
Referencia: [foto de perfil en Microsoft Graph](https://learn.microsoft.com/en-us/graph/api/profilephoto-get?view=graph-rest-1.0).

La lectura y escritura delegadas están limitadas por los permisos de la cuenta
conectada. Este registro permite elegir carpetas en sitios donde el usuario pueda
escribir, sin una asignación `Sites.Selected` adicional. Es un alcance de archivos
más amplio que el registro nuevo inicial, adoptado al reutilizar la aplicación
que el usuario propuso para explorar y guardar en sus rutas existentes.

MSAL usa navegador del sistema, código de autorización con PKCE y renovación
silenciosa. Windows protege los tokens con DPAPI. Identificadores públicos en
`workbench/sharepoint_app.json`; caché, rutas y cola en runtime, fuera de Git.
**Desconectar** elimina la sesión local de Workbench; no cierra la sesión general
Microsoft del navegador ni cambia la configuración del registro reutilizado.

## Elegir carpetas

1. Abrir **SharePoint** y conectar una cuenta CHC. Si estaba conectada
   antes de cambiar el registro, renovar la conexión con **Cambiar cuenta**.
2. Pulsar **Elegir carpeta** en la tarjeta de SharePoint. Buscar un sitio si hace falta.
3. Elegir sitio, biblioteca y carpeta; pulsar **Usar esta carpeta para todos**.
4. Ejecutar los bots o exportar sus resultados guardados. Se organizan localmente.
5. Pulsar **Actualizar**, seleccionar el mes y accionar **Subir a SharePoint**.
   Solo entran bots/procedimientos completos, al día hasta la última fecha
   consultable, o cerrados manualmente en la bitácora mensual.

## Elegir descargas guardadas — 25/11/2026

El flujo principal ya no exige localizar archivos en Windows:

1. Abrir **SharePoint → Resultados → Elegir descargas guardadas…**.
2. Filtrar por procedimiento, mes, año y/o nombre. Aparecen las descargas conocidas
   por los catálogos e historiales de la app, aunque aún no tengan CSV.
3. Marcar varias filas. Para Contenedores de julio y agosto de 2026, elegir
   Contenedores, año 2026 y marcar ambos. También se puede filtrar un mes, usar
   **Seleccionar visibles**, cambiar al otro y añadirlo: no pierde la selección.
4. Si faltan archivos, pulsar **Generar CSV seleccionados**. Se generan desde los
   resultados SQLite de esos lotes sin cambiar la ejecución activa ni consultar
   TICA. Se omiten procesos ocupados y se informa del resultado. Generar no sube.
5. Revisar las rutas de las filas y pulsar **Subir seleccionados (N)**. Cada CSV
   va a su ruta de procedimiento, mes y modalidad, bajo la carpeta común elegida.

No se exige cierre mensual para esta selección y no se modifica la bitácora.
**Quitar selección** desmarca todo. El contador incluye las filas marcadas que
quedaron ocultas al cambiar filtros. **Actualizar** relee las descargas y mantiene
las identidades que todavía existan. Los CSV sustituidos y Contenedores
Aéreo/Terrestre permanecen fuera de esta lista.

La generación manual se agrupa por proceso y por IDs únicos de ejecución; no
recorre otros lotes ni cambia configuraciones. Si un lote contiene varias
modalidades, su exportador conserva las salidas de ese lote; solo se suben las
filas elegidas. Los BLs antiguos sin períodos verificables aparecen por preparar:
al exportar se obtienen los meses/modos reales del payload, sin deducirlos del
nombre. Después se eligen las salidas concretas mostradas en la lista.

`chc_cloud/download_catalog.py` lee únicamente metadatos y registros existentes,
sin abrir servicios de bots ni generar archivos. Los workers conservan sus
exportadores y añaden `export_selected`, validando todos los IDs antes de actuar.
El envío vuelve a validar catálogo, archivos vigentes y destino, captura las
copias y limita la sincronización a sus identidades. No envía otros pendientes.
Los conflictos de propietario, huella y `eTag` conservan las protecciones anteriores.

La revisión local confirmó julio/agosto en el historial de Contenedores; no estaban
en el registro de CSV públicos usado por el selector anterior. No se exportaron
ni subieron sus datos reales durante las pruebas. Pasaron 48 pruebas offline
distintas y el smoke QML, con Graph simulado y almacenamiento temporal: catálogo
sin CSV, cuatro catálogos DUA separados, períodos BLs, selección múltiple,
generación por IDs, cancelación/ocupados, cuentas/rutas y cola existente. La
prueba de QML ejecuta filtrar → marcar julio/agosto → generar → subir ambos a
rutas distintas, sin incluir septiembre; comprueba dos filas y botones accesibles
en 1280×774, 1000×680 y 1000×600. No hubo avisos QML ni consultas reales.

La app se abrió sin consultas antes de documentar; no se actualizó la distribución
empaquetada. Evidencia sintética pequeña en
`runtime/diagnostics/saved-downloads-20261125/`.

## Subir un CSV individual — 25/11/2026

Para descargas guardadas aparte, como Contenedores de julio y agosto de 2026,
ya no es necesario que el mes figure en la lista mensual:

1. Abrir **SharePoint → Resultados → CSV externo…** (opción secundaria).
2. Elegir un CSV existente. Se admiten los generados por Workbench y archivos
   externos, incluso fuera de la carpeta madre local. Si solo existe SQLite,
   primero usar **Más → Generar CSV de esta ejecución/tabla** en el bot.
3. Revisar procedimiento, mes/año, modalidad y carpeta de destino. Los datos del
   nombre sirven solo como propuesta; un archivo externo permite corregirlos.
   Si faltan datos o se cambian, pulsar **Revisar destino**.
4. Comprobar la ruta mostrada y pulsar **Subir este CSV**. Para julio y agosto,
   elegir y enviar cada archivo por separado. No se inicia ningún otro envío.

Esta acción copia únicamente el archivo elegido; no exige cierre mensual, no
marca el mes completo y no modifica pendientes de los bots. El selector por mes
conserva sus condiciones anteriores. Contenedores admite únicamente Marítimo;
no se vuelven a habilitar sus históricos aéreos/terrestres.

Los CSV registrados conservan nombre, ruta relativa y propietario. Un CSV externo
utiliza la estructura común de bot/procedimiento, mes y modalidad, con el sufijo
`ARCHIVO_<nombre original>` para distinguirlo del acumulado mensual. La ruta final
se muestra antes de confirmar. No se renombra ni modifica el archivo local; sus
bytes, columnas, codificación y ceros se copian intactos. Elegir otro archivo
invalida la selección anterior, incluso si la nueva inspección falla.

La preparación captura la huella del CSV y el destino revisado. Si el archivo,
su registro, la cuenta o la carpeta cambian, se exige volver a revisar/seleccionar.
Se conservan controles de propietario y `eTag`: la primera subida no reemplaza
archivos preexistentes, y otro lote/archivo no puede sobrescribir una publicación
ajena. No se admite un CSV que el registro haya sustituido por un acumulado nuevo.

Si falla la red, la copia exacta queda en la cola independiente con la indicación
**CSV individual** en Actividad. Abrir la app o publicar otro mes no la envía;
**Reintentar envíos** la recupera con la misma cuenta y destino, sin exigir cierre
mensual. Las copias mensuales siguen comprobando cobertura. Ninguna de estas
acciones consulta TICA ni cambia las bases de resultados.

Implementación en `chc_cloud/manual_upload.py`, `service.py`, el puente Qt y
`ManualUploadDialog.qml`. La autorización individual se guarda en el destino
capturado de su entrada de cola; no migra esquemas ni añade credenciales/permisos.
Se verificó con 36 pruebas offline distintas y el smoke QML: archivos externos
de julio/agosto, alcance de un solo envío, revisión sin subida, recuperación,
huella/propietario/`eTag`, cuenta/destino cambiados, cola mensual y worker real
sin sesión. La interfaz y sus botones se comprobaron en 1280×774, 1000×680 y
1000×600, sin avisos QML. No se hicieron subidas reales ni consultas TICA.
La app se abrió antes de documentar y se conservó abierta durante el ajuste final
de invalidación de selección. No se actualizó la distribución empaquetada.
Evidencia sintética pequeña en `runtime/diagnostics/manual-sharepoint-20261125/`.

## Perfil, archivos y actividad — 18/10/2026

El círculo de la barra superior es el acceso a la cuenta: foto circular o
iniciales, nombre/correo y acciones de conectar/cambiar cuenta, actualizar perfil,
abrir SharePoint y desconectar. `AccountAvatar.qml` dibuja la imagen local en un
recorte circular; Qt nunca recibe tokens ni consulta Graph directamente.

SharePoint se organiza en Resultados, Archivos y Actividad. Resultados concentra
carpetas madre, botones de abrir/explorar y selección mensual con CSV/bots listos.
El explorador muestra carpetas y archivos (tamaño, fecha y apertura en navegador),
con acceso al destino guardado sin volver a elegirlo. Nueva carpeta exige acción
explícita y nombre válido; Graph usa conflicto fail, sin copias con sufijo ni
sobrescritura. No modifica el destino ni la cola de envíos. Los clics siguen
pasando primero identidad al diálogo para resistir la destrucción de delegados.
Actividad muestra los últimos 50 envíos con búsqueda/filtros, fecha, estado y
motivo de error; los contadores globales proceden de toda la cola SQLite.

`CloudAccount.token` mantiene los ámbitos Files/Sites separados de User.Read
para conservar sesiones anteriores. Conectar solicita los tres; si falta la
sesión de perfil, Cambiar cuenta la renueva. `profile.py` obtiene `/me` y la foto
solo con User.Read; 404 significa sin foto, no error de archivos. La caché local
queda bajo `runtime/workbench/sharepoint/`, asociada al home_account_id mediante
hash. Cambiar de usuario no muestra la foto anterior y desconectar limpia el
perfil. Si falla actualizar foto conserva la copia de la misma cuenta; errores
de red/consentimiento/perfil no abortan el estado ni las publicaciones. Foto solo
JPEG/PNG de hasta 4 MiB; sin redirecciones ni tokens fuera de Graph.

La navegación sigue limitada al sitio/biblioteca elegidos y crear carpetas al
último padre consultado. El acceso directo al destino comprueba su cuenta
propietaria. La app conserva reglas de propietario/eTag, CSV/mes listos y envíos
exclusivamente explícitos. Ninguna de estas funciones envía correo o usa Power BI.

Validación nueva: 31 pruebas offline (20 existentes cloud, 8 perfil/navegación
y 3 Qt/worker/cifrado), más smoke de seis vistas. Cubren User.Read independiente,
cache/reinicio/cambio de cuenta/404/fallo de red, MIME y redirecciones, paginación
de archivos, creación explícita acotada, avatar y navegación QML, filtros y ausencia
de subidas al abrir/navegar. Capturas con identidad/foto sintéticas a 1280×820
oscuro y 1000×600 claro en `runtime/diagnostics/sharepoint-ui/`. No se usó la cuenta
real ni se crearon carpetas/subidas reales para probar este cambio. La app activa
se conservó antes de documentar; interfaz nueva al próximo arranque.

**Completo no significa 100 % guardados en todos los bots.** La comprobación
automática de Detalles exige todos sus DUAs confirmados. Tránsito, Talón y XMovimientos
pueden completar con días omitidos y pendientes excluidos del resultado final.
Manifiestos admite exclusiones y pendientes con tres intentos agotados al finalizar
la ejecución; BLs admite intentos agotados en ejecuciones terminadas, nunca una
interrupción como cierre. Vacíos verificados de XMovimientos cuentan aparte.
Los pendientes y páginas parciales omitidas se conservan para reintentos.

Por petición del 17/10/2026, todos los bots admiten aceptación manual aunque
conserven pendientes, incluido Detalles. En los cuatro DUA, **Calendario → Marcar
completado** aporta ese día al cierre mensual y a los contadores de Vista general;
se distinguen días verificados y manuales. Cuando cubren el mes aparece
**Completado manual** y sus CSV quedan habilitados para **Subir a SharePoint**.
En el mes actual la cobertura hasta la fecha consultable aparece **Al día (manual)**.
BLs y los cinco procedimientos de Manifiestos usan el cierre manual mensual.
La marca de día persiste tras **Reintentar día/mes**, que sigue consultando solo
los pendientes. Quitarla vuelve a comprobar la cobertura y la elegibilidad del CSV.
Marcar, actualizar o cerrar manualmente nunca inicia una subida.

Para el mes actual, **Al día** exige cobertura hasta el último día consultable,
respetando las 00:01 de Costa Rica. Al aparecer un nuevo día vuelve a comprobarse.
En Vista general, **Cierre manual…** permite marcar completo un bot/procedimiento
o volver a la comprobación automática. Se guarda separado del progreso; no cambia
estados ni inventa filas. Nuevos datos o intentos invalidan la marca anterior.
Esto último corresponde al cierre del mes; las marcas individuales del calendario
se conservan hasta retirarlas expresamente. La lista de meses subibles se actualiza
al refrescar la bitácora si la cuenta está conectada, sin enviar archivos.

La carpeta local predeterminada es `RESULTADOS/`, configurable desde esta pantalla.
El destino online replica los mismos nombres y subcarpetas, todos en mayúsculas:

```text
CARPETA_MADRE/
  DETALLES/OCTUBRE_2026/DETALLES_OCTUBRE_2026.CSV
  DUAS_TRANSITO/OCTUBRE_2026/DUAS_TRANSITO_OCTUBRE_2026.CSV
  TALON/OCTUBRE_2026/TALON_OCTUBRE_2026.CSV
  XMOVIMIENTOS/OCTUBRE_2026/XMOVIMIENTOS_OCTUBRE_2026.CSV
  BLS/OCTUBRE_2026/BLS_MARITIMO_OCTUBRE_2026.CSV
  MANIFIESTOS/CONOCIMIENTOS/OCTUBRE_2026/MANIFIESTOS_CONOCIMIENTOS_AEREO_OCTUBRE_2026.CSV
```

Los cinco procedimientos de Manifiestos tienen carpetas propias. BLs divide por
el mes y modo reales de cada manifiesto, conservando filas y columnas. Selecciones
parciales, filtros y lotes manuales agregan un sufijo para evitar sustituir otro
conjunto de datos. Si no se conoce el mes, se usa `SIN_PERIODO`; no se inventa una fecha.

La URL `https://chcconsultorescr.sharepoint.com/_layouts/15/sharepoint.aspx/onedrive/places`
abre el catálogo de sitios. Los enlaces `FileBrowser.aspx` con `id`/`listurl` y las
vistas Forms con `RootFolder` se normalizan al sitio real. Graph devuelve sitios
según la cuenta, pagina respuestas y filtra al host SharePoint de CHC. La lista
puede incluir sitios adicionales a los recientes mostrados por Edge.

Se copian exclusivamente CSV de resultados, con sus columnas, codificación y
datos intactos. SQLite, TXT/JSON de pendientes y diagnósticos siguen locales.
Las exportaciones manuales de los bots actualizan únicamente sus CSV
locales y un registro de salidas públicas. Ninguna acción de SharePoint inicia
consultas TICA. Los archivos históricos se conservan en sus rutas anteriores;
usar **Exportar** en el lote vuelve a generar sus datos guardados con la estructura
común, sin descargar de nuevo. Cambiar la carpeta madre no mueve archivos existentes.

En los acumulados de Manifiestos, el CSV mensual de una modalidad sustituye como
salida final a los parciales del mismo lote, mes y modalidad. Los archivos anteriores
se conservan localmente, pero no se incluyen otra vez en **Subir a SharePoint**;
sus envíos pendientes se pausan si ya fueron sustituidos. Las otras modalidades,
otros propietarios y las selecciones filtradas conservan sus propias salidas.
No se borran copias históricas que ya estuvieran en SharePoint.

## Pendientes y conflictos

La cola online es independiente y persistente. Sin sesión o red conserva copias
pendientes de envíos pedidos por el usuario; requiere un reintento explícito
con la cuenta y destino compatibles. Los envíos mensuales exigen que el mes siga
completo, al día o cerrado manualmente; los CSV individuales conservan su
autorización explícita sin modificar la bitácora.
Los errores se muestran y se recuperan con **Reintentar envíos**. Retirar o cambiar
un destino pausa sus copias anteriores y conserva los CSV locales.

Una primera subida no reemplaza archivos preexistentes. Las actualizaciones de
archivos publicados por Workbench conservan su identificador y `eTag`; se rechazan
cambios o movimientos externos. Lotes diferentes tampoco pueden compartir el
mismo nombre y destino. Resolver un conflicto o elegir otra carpeta antes de
reintentar; el original online y el CSV local se conservan.

## Implementación y pruebas

`chc_cloud/` contiene MSAL, Graph y cola SQLite. `sharepoint_bridge.py` inicia un
proceso propio del entorno Workbench, separado de todos los bots. Configuración,
cola, caché DPAPI y publicaciones online viven en `runtime/workbench/sharepoint/`.
El contrato local está en `chc_runtime/output_layout.py`; configuración y registro
comunes en `runtime/workbench/exports.json` y `publications.sqlite3`.
Los eventos `published` se emiten tras la exportación local atómica, sin conectar
con envíos online. Al cerrar se conservan envíos inconclusos para un reintento
manual. Las rutas por bot y avisos automáticos de la versión inicial se conservan
como históricos y no se envían automáticamente.

Validación: 19 pruebas cloud con transporte simulado, dos de Qt/worker/cifrado
Windows, cuatro del contrato de salidas y smoke QML. Exportaciones y recuperación
comprobadas con portales locales de Detalles, Tránsito, Talón/XMovimientos,
calendario diario y cinco procedimientos de Manifiestos con entrega a BLs.
17 comprobaciones de bitácora y una de Qt cubren omitidos, Detalles estricto,
mes actual, cierre manual persistente/reversible y su invalidación al cambiar datos.

El selector procesa clics desde funciones del diálogo, fuera de los delegados
de las listas: cambiar sitio o recibir una respuesta recrea esas filas y antes
interrumpía la navegación. La prueba Qt recorre sitio → biblioteca → subcarpeta,
incluye notificaciones síncronas y comprueba selección de una carpeta sin subcarpetas.

Pruebas reales autorizadas del 14 de octubre de 2026:

- OAuth con el registro existente y cuenta CHC: satisfactorio.
- Graph devolvió 7 sitios. En Automatización TIC@ se leyeron Documentos y sus 15
  carpetas originales; en TIC@_DUASxREGIMEN, Documents y 8 carpetas.
- El selector Qt mostró esos 7 sitios y recorrió Automatización TIC@ / Documentos.
- Por petición expresa se creó la carpeta `CHC_Workbench_Prueba_20261014_163132`
  dentro de Automatización TIC@ / Documentos. `prueba_conexion.txt` se subió,
  descargó y comparó byte a byte; se actualizó con `eTag` y se verificó otra vez.
  El archivo de prueba se dejó disponible para revisión. Evidencia local en
  `runtime/sharepoint-write-test/report.json`.
- No se asignaron destinos a bots ni se enviaron sus CSV de producción. Estas
  comprobaciones no prueban que Power BI haya actualizado sus datos.

[Archivo de prueba](https://chcconsultorescr.sharepoint.com/sites/AutomatizacinTIC/Documentos%20compartidos/CHC_Workbench_Prueba_20261014_163132/prueba_conexion.txt).

## Registro inicial conservado

Inicialmente se creó **CHC Workbench · Resultados SharePoint**, cliente
`da7ff4b7-8a2e-4c49-9338-17975a058a99`, con `Sites.Selected` delegado y retorno
`http://localhost`. La conexión funcionó, pero la lectura sin asignación devolvió
403. El usuario agregó `Sites.Read.All`; Microsoft exigió aprobación administrativa.
Por ello propuso reutilizar OAuth2 par CHC REPORTES, que sí completó la conexión
con los ámbitos necesarios. El registro nuevo se conserva y ya no es el usado por
Workbench; la falta de aprobación de ese registro no bloquea al vigente.

Referencias oficiales: [búsqueda de sitios](https://learn.microsoft.com/en-us/graph/api/site-search?view=graph-rest-1.0),
[registro de escritorio](https://learn.microsoft.com/en-us/entra/identity-platform/scenario-desktop-app-configuration),
[MSAL Python](https://msal-python.readthedocs.io/en/latest/),
[cargas por sesión](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0).

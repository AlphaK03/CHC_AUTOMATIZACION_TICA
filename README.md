# CHC Workbench — Automatización TICA

Repositorio modular para mantener BLs, Detalles, DUAs Tránsito, Talón,
XMovimientos y Manifiestos en un solo lugar, con preparación de bases integrada.

**Estado actual: seis módulos integrados en QML, incluidos BLs y Manifiestos.**
El panel utiliza el símbolo vectorial de CHC en la navegación y Acerca de,
con icono propio de Windows y recursos incluidos en el repositorio.
Durante la carga de bases aparece una espera animada con los bots que siguen
preparándose. Los controles se habilitan automáticamente al terminar la carga.
Los seis bots comparten un resumen visual de progreso: cifras destacadas,
porcentaje, barra por estados y contadores alineados. BLs y Manifiestos muestran
las modalidades juntas para comparar su avance; se adapta a ambos temas y al ancho.
Manifiestos reúne cinco procedimientos independientes y genera bases locales
para BLs. Una segunda apertura activa la misma ventana de la plataforma.
La preparación y el motor de BLs admiten números de manifiesto con una letra
final, como `2601287L`, conservando el identificador y sus ceros sin cambios.
En **BLs → Más → Reconsultar BLs con 0 filas…** se pueden volver a consultar
los guardados vacíos del lote elegido, con confirmación y respaldo. Conserva
historial, BLs con líneas y otros pendientes; actualiza el CSV con las líneas nuevas.
BLs muestra un resumen por modalidad con **guardados/total**, estado, pendientes,
trabajos en curso, filas confirmadas y BLs sin líneas. Permite ver si Marítimo
terminó mientras Aéreo sigue descargando, contando todo el lote.
La lista de los cinco procedimientos de Manifiestos distingue **Marítimo,
Aéreo y Terrestre** en cada fila, con conteos propios y filtro de modalidad.
Las descargas existentes se muestran desde SQLite sin volver a consultarlas.
La interfaz reserva espacio para varias filas y adapta navegación, páginas y
ventanas al tamaño disponible. Los contenidos largos tienen desplazamiento
visible; calendarios, bases y SharePoint conservan sus controles dentro de la ventana.
Los seis bots permiten eliminar sus tablas/ejecuciones guardadas con respaldo y
confirmación escrita **BORRAR**. En Manifiestos y BLs: seleccionar una ejecución
y abrir **Más → Eliminar base de datos…**; conserva entradas originales y CSV.
En los cuatro DUA se encuentra en **Base de datos**; limpiar o quitar filas
también exige **BORRAR**. Las operaciones quedan bloqueadas mientras trabajan.
Los cuatro bots DUA recuperan transacciones SQLite interrumpidas al arrancar,
con respaldo previo y bloqueo exclusivo; abrir el panel conserva resultados,
intentos y reservas sin iniciar consultas.
En Diario automático basta pulsar Iniciar para retomar el primer día pendiente.
El rango visible avanza con el progreso, continúa con los días disponibles y
espera hasta las 00:01 de Costa Rica cuando queda al día.
Si una actualización de la lista coincide con un guardado y SQLite está ocupada,
conserva la vista y vuelve a leerla sin marcar la descarga como fallida.
En el calendario de los cuatro bots DUA, **Marcar completado** pone un día en
verde como **Completado manual**. La marca es reversible y se conserva al reabrir;
**Reintentar día/mes** sigue consultando sus pendientes. Los días aceptados cuentan
en Vista general para completar el mes y habilitar **Subir a SharePoint**, con
conteos separados de días verificados y manuales; no modifica resultados.
Vista general incluye una bitácora mensual de los seis bots: estados reales,
meses completos verificados y detalle de los cinco procedimientos de Manifiestos.
Cada bot muestra el conteo de días como **16/31**, en blanco y negrita.
Se actualiza leyendo el progreso guardado, sin iniciar consultas.
La comprobación automática de Detalles exige todos los DUAs descargados; los otros
bots admiten omitidos fuera del resultado final. Todos aceptan cierre manual con
pendientes conservados. El mes actual puede aparecer **Al día** hasta la última
fecha consultable. **Cierre manual…** permite cerrar un bot/procedimiento o volver
a la comprobación automática, conservando pendientes para reintento.
En DUAs por manifiesto, las exclusiones por `frmAmbiente` cuentan como omitidas:
una ejecución **Finalizada con exclusiones** permite **Al día** o **Completado**
según su cobertura. El reintento normal no reabre estas exclusiones.
[Uso de la bitácora](workbench/README.md#bitácora-mensual).

**Cuenta y SharePoint** conecta opcionalmente una cuenta CHC y permite elegir una
carpeta madre local y una online para todos los bots. Los CSV públicos comparten
nombres en mayúsculas y organización por bot, mes y modo cuando aplica.
La subida se inicia solo mediante **Subir a SharePoint** o un reintento explícito.
El selector recorre sitios, bibliotecas y subcarpetas; también permite elegir la
raíz de una biblioteca o una carpeta sin subcarpetas. [Guía de SharePoint](docs/SHAREPOINT.md).

Los paneles de actividad conservan el mensaje y la posición al leer el historial.
Solo siguen automáticamente las novedades cuando el lector está al inicio.
Las consultas en curso aparecen primero y en una zona fija: DUAs en Actividad;
BLs con manifiesto, BL, página y filas acumuladas en «Descargando ahora».
XMovimientos distingue **Vacío**, **Vacío por verificar** y **Error**. Los vacíos
confirmados permiten avanzar el calendario y se pueden volver a consultar desde
**Base de datos → Reintentar vacíos**, sin generar filas ficticias en el CSV.
Vista general también permite elegir un mes terminado, marcar los bots/procedimientos
y asignar trabajadores antes de **Iniciar seleccionados**. Retoma avances y mantiene
los procesos ocupados; BLs espera Conocimientos completos del período elegido.
[Inicio conjunto por mes](workbench/README.md#inicio-conjunto-por-mes).

Los procedimientos de Manifiestos se eligen en una barra horizontal con el estilo de la navegación
lateral; cada uno ofrece Procesamiento y Configuración, como los otros bots.
El nombre de tabla se genera por período (`octubre26`, `enero27`) y se retoma la
acumulación del mes al ampliar fechas o cambiar las modalidades: consulta de nuevo
el listado y descarga únicamente manifiestos nuevos o pendientes. Los CSV siguen
separados por modalidad; los filtros de Courier, IDs o límite permanecen aislados.
[Uso, contratos y límites comprobados](docs/INTEGRACION_MANIFIESTOS.md).
BLs permite elegir directamente meses y modalidades con descargas completas de
Conocimientos; genera su base Courier=N e inicia su motor sin elegir archivos.
Al repetir la misma selección de meses y modalidades, amplía el lote existente
con los BLs nuevos y retoma sus pendientes sin repetir los guardados. Conserva
sus páginas, historial y CSV acumulados; otra selección de mes/modo queda separada.
Su lista muestra la fila, manifiesto y BL originales; conserva los contadores
durante la preparación y permite continuar únicamente los pendientes.
También muestra página y filas acumuladas por BL. Las páginas verificadas se
guardan para retomar una descarga interrumpida, sin confirmar un BL parcial.
La búsqueda acepta respuestas GET y POST verificadas de TICA; un timeout queda
pendiente y no se interpreta como un BL inexistente.
[Conexión BLs–Conocimientos](docs/BLS_DESDE_CONOCIMIENTOS.md).
Detalles importa bases a SQLite, consulta TICA, retoma pendientes, administra tablas
y exporta con el motor actual. Esta rama añade **Diario automático**: base propia
sin Excel, calendario y acumulación mensual. Tránsito usa la misma infraestructura
con su extracción de líneas y base propia del régimen TRANSITO. Talón y
XMovimientos conservan sus extracciones v2, SQLite y base diaria de importación
compartida. [Uso y alcance de Tránsito](docs/INTEGRACION_TRANSITO.md) y de
[Talón/XMovimientos](docs/INTEGRACION_IMPORTACION.md).
Los regímenes sin movimientos no bloquean la base diaria: se aceptan como vacíos
solo con respuesta confirmada de TICA; los errores conservan el estado pendiente.

Para abrir: doble clic en **`Abrir_Workbench.bat`**. En un equipo nuevo ejecutar
primero `Instalar_Workbench.bat` y los instaladores de cada módulo:
`Instalar_Detalles.bat`, `Instalar_Transito.bat`, `Instalar_Talon.bat` y
`Instalar_XMovimientos.bat`, `Instalar_Manifiestos.bat` e `Instalar_BLs.bat`.
Para bases automáticas DUA: `Instalar_Base_Diaria.bat`. Consultar el
[manual del Workbench](workbench/README.md) y la [integración de Detalles](docs/INTEGRACION_DETALLES.md).

Capturas del prototipo: [vista general oscura](docs/preview/workbench-dark.png),
[espacio de Detalles](docs/preview/workbench-detalles.png) y
[tema claro con barra contraída](docs/preview/workbench-light.png).
Vista operativa actual: [Detalles integrado](docs/preview/detalles-integrado.png).
Nuevos módulos: [Talón](docs/preview/talon-integrado.png) y
[XMovimientos](docs/preview/xmovimientos-integrado.png).

## Objetivo final del proyecto

Construir **CHC Workbench**, una plataforma de escritorio que reúna las
automatizaciones TICA de CHC en una sola aplicación y un solo repositorio.
El usuario podrá acceder a cada bot desde una navegación lateral expandible,
trabajar en espacios independientes y administrar bases, consultas, progreso
y resultados desde la misma plataforma.

La unificación facilitará mantenimiento y crecimiento: módulos con reglas propias
y servicios comunes donde corresponda. Agregar un bot no debe exigir reescribir
la plataforma ni duplicar otra aplicación completa.

La independencia incluye **las bases de entrada**. Más adelante se integrarán
DUAS_SCRAPPING y los demás generadores/separadores necesarios para prepararlas
dentro del Workbench, sin abrir aplicaciones auxiliares o unir archivos manualmente.
El usuario podrá generar una base, enviarla a uno o varios módulos y revisar sus
resultados en el mismo entorno. TICA y el navegador siguen siendo requisitos externos.

**Autonomía solicitada:** Detalles usa Total_DUAS, Tránsito usa la base de Tránsito,
y Talón/XMovimientos usan Importación. Cada bot deberá generar su base sin elegir
Excel, para meses terminados o en un ciclo diario: descargar ayer, procesarlo,
esperar hasta las 00:01 y continuar, recuperando días atrasados y acumulando el CSV
del mes correspondiente. Los cuatro consumidores DUA tienen integración diaria.
Talón y XMovimientos reutilizan la misma caché verificada para evitar descargas
duplicadas. Consultar [uso y límites del piloto](docs/PILOTO_DETALLES_DIARIO.md)
y el [contrato completo](docs/AUTOMATIZACION_DIARIA.md).

El destino va más allá de un menú de ejecutables: motores con contratos comunes
de entrada, ejecución, detención, eventos y exportación, preservando validaciones,
esquemas, ceros iniciales y recuperación. El acceso inicial por procesos separados
será una transición técnica cuando se autorice integrar los motores.

**Tecnologías del panel:** Python + PySide6 + Qt Quick/QML. Python conserva lógica
y automatización; QML define pantallas y componentes. SQLite es la persistencia
local; Playwright es el motor activo de los cinco bots copiados. En uso normal,
Detalles, Tránsito, Talón y XMovimientos ejecutan sus motores en procesos propios.
`chc_runtime/` comparte persistencia, protocolo y coordinación. Manifiestos y BLs
tienen adaptadores propios por manifiesto/conocimiento y motores originales aislados.
`--demo` desactiva todos los motores reales para comprobar solo la interfaz.

El [contexto para otra sesión](docs/CONTEXTO_PROYECTO.md) registra decisiones,
restricciones, estado y cómo continuar. El [plan](docs/PLAN_IMPLEMENTACION.md)
organiza las fases de implementación.

## Organización

```text
CHC_AUTOMATIZACION_TICA/
  bots/
    bls/                 # BLs_BOT: código actual de la raíz
    detalles/            # Detalles_BOT: código actual de la raíz
    duas_transito/       # DuasTransito BOT: contenido actual de v2/
    talon/               # Talon_BOT: contenido actual de v2/
    xmovimientos/        # XMovimientos_BOT: contenido actual de v2/
    manifiestos/         # Cinco procedimientos y generador de bases BLs
  workbench/             # Panel QML, puente de Detalles, demos y registro
  chc_runtime/           # Infraestructura operativa común y perfiles por bot
  integrations/          # Generadores de bases: integración futura
  docs/                  # Plan, arquitectura, inventario y trazabilidad
  tools/                 # Mantenimiento y verificaciones; prueba real solo explícita
```

Cada bot conserva su propio `src/`, recursos y dependencias. Se elimina solamente
el nivel externo `v2/` de los tres módulos que lo usan: sus rutas internas relativas
a `src/` siguen resolviendo a la raíz del módulo. No se fusionan paquetes llamados
`core`, `ui`, `flows` o `utils`; aún no son una biblioteca común.

Los orígenes se mantienen intactos. La copia incorpora cambios locales guardados
en disco, incluidos archivos sin confirmar en Git. No importa historiales Git,
entornos virtuales, ejecutables, datos de producción, progreso ni rutas personales.
Los tres `Names_TicaPortal.xlsx` de los módulos v2 se incluyen como **recursos de
ejecución**, no como bases de trabajo. Detalles usa `config/captcha_lookup.json`.

## Documentación

- [Plan y prioridades](docs/PLAN_IMPLEMENTACION.md).
- [Contexto completo para otra sesión](docs/CONTEXTO_PROYECTO.md).
- [Abrir y probar la interfaz](workbench/README.md).
- [Detalles: uso, matriz de funciones y evidencia](docs/INTEGRACION_DETALLES.md).
- [Arquitectura propuesta](docs/ARQUITECTURA.md).
- [Inventario y dependencias observadas](docs/INVENTARIO.md).
- [Registro de módulos](workbench/modules.json).
- [Copia y verificación](docs/MIGRACION.md).
- [Estado de esta entrega](docs/ESTADO_INICIAL.md).
- [Integración futura de bases](integrations/README.md).
- [Bases por bot y autonomía mensual/diaria](docs/AUTOMATIZACION_DIARIA.md).
- [Piloto diario de Detalles: uso y calendario](docs/PILOTO_DETALLES_DIARIO.md).

## Comprobar esta entrega

**Cuenta y SharePoint** permite conectar opcionalmente una cuenta CHC y elegir
una carpeta madre online para todos los bots. La carpeta madre local es también
común; los CSV se organizan por bot, mes y modo, con nombres en mayúsculas.
**Subir a SharePoint** envía únicamente resultados de bots completos, al día o
cerrados manualmente en la bitácora, cuando el usuario lo solicita.
Exportar localmente no inicia subidas. La aplicación conserva su funcionamiento
y resultados locales sin cuenta. Registro OAuth2 de escritorio
reutilizado de CHC REPORTES con `Sites.Read.All` y `Files.ReadWrite.All` delegados,
para explorar sitios y guardar archivos según los permisos de la cuenta.
Véase [configuración y uso](docs/SHAREPOINT.md).

Los casos pendientes y guardados cuentan con **Abrir en TICA**, que abre un navegador visible
para revisar el DUA, BL o manifiesto sin cambiar su estado ni detener descargas.
En modo diario, Detalles, Tránsito, Talón y XMovimientos realizan como máximo tres
intentos automáticos por pendiente. Al agotarlos, el día queda **Omitido** y el bot
continúa. **Reintentar mes** o **Reintentar día** permite solicitar otra ronda de
hasta tres intentos para los pendientes; los resultados guardados se conservan.

Desde la raíz, con Python 3.12 y sin instalar dependencias de los bots:

```powershell
py -3.12 tools/verify_import.py
```

Comprueba SHA256 de cada archivo copiado, los puntos de entrada y la sintaxis
Python sin importar ni ejecutar motores. No abre ventanas ni consulta el portal.
Los informes y manifiestos están en `docs/migration/`.

Para comprobar la interfaz:

```powershell
.\workbench\.venv\Scripts\python.exe workbench/app.py --smoke-test
.\workbench\.venv\Scripts\python.exe -m unittest discover -s workbench/tests -v
```

## Ejecutar un módulo por separado

Los puntos de entrada están registrados en `workbench/modules.json`. Para operar,
preparar primero un entorno propio y revisar el README del módulo. Ejemplo para BLs:

```powershell
Set-Location bots/bls
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run_bot.py
```

Detalles usa `python src/main.py`. Tránsito, Talón y XMovimientos también usan
`python src/main.py` desde sus nuevas raíces, con su `requirements.runtime.txt`.
Estos tres archivos de dependencias son una base derivada de los imports actuales;
su instalación y ejecución aún requieren validación. Chromium también debe estar
disponible; BLs incluye su preparación automática. La configuración nueva parte
de valores predeterminados y no reanuda lotes de las aplicaciones originales.

No usar los specs originales de Tránsito/Talón/XMovimientos para generar la
distribución nueva: contienen rutas al repositorio anterior y se conservaron
solamente en `docs/reference/`. Su adaptación corresponde a la fase de empaquetado.

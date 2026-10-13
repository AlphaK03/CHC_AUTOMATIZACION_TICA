# Consulta DUAs — AstraCode

Descarga los DUAs de TICA por año, mes, régimen y rango. Guarda primero las
respuestas verificadas en SQLite y genera los tres Excel que consumen los otros bots.

## Uso

```powershell
python -m pip install -r requirements.txt
python src/main.py
```

1. Seleccionar régimen (o Todos los regímenes), mes, año y rango.
2. Iniciar: los rangos ya guardados se reutilizan. Si una descarga falla, se divide
   en dos para la siguiente ronda; no se vuelve a consultar una parte que tuvo éxito.
3. Para renovar una descarga existente, marcar **Volver a descargar rangos guardados**.
4. **Unir archivos finales** conserva los modos Primera parte, Segunda parte y Ambas
   partes. Exige cobertura verificada de todos los regímenes para ese período/rango.
   También exporta los originales por régimen: mensuales si se unen ambas partes,
   o las quincenas disponibles si se une una parte.
5. Esperar **Unificación completada** antes de abrir los Excel o iniciar los bots
   consumidores. La carpeta de salida sigue siendo configurable.
6. Para obtener solo los originales, usar **Exportar originales…** y elegir
   **Dos partes** o **Mes entero**. Usa el mes y año seleccionados; no consulta TICA
   ni modifica los tres archivos finales.

Edge y su WebDriver deben tener versiones compatibles. El botón **Actualizar
WebDriver** conserva la actualización del controlador configurado. No se utiliza
Selenium Manager para reemplazar silenciosamente esa selección.
La ruta predeterminada nueva es `drivers/msedgedriver.exe` junto a la app, para
mantener un controlador propio. Una ruta que ya esté guardada en Configuración
se respeta. La entrega local incluye un controlador compatible con el Edge instalado
al preparar esta versión; cuando Edge se actualice, usar **Actualizar WebDriver**.

La carpeta de salida y todas sus subcarpetas se crean al exportar. Una ruta vacía
usa `DUAs_2025` junto a la app; una ruta relativa parte de la carpeta de la app,
independientemente de dónde se abrió el acceso directo. También se admiten rutas
copiadas entre comillas y variables de entorno del equipo actual.
Las operaciones de archivo en Windows usan internamente rutas extendidas, incluso
para los temporales y respaldos, para funcionar cuando superan 260 caracteres sin
cambiar el registro ni requerir permisos de administrador. Los mensajes muestran
la ruta normal. Si la carpeta no permite escritura o la unidad no está disponible,
la app muestra el motivo antes de preparar los Excel.

## Clasificación preservada

| Archivo | Regímenes incluidos |
| --- | --- |
| `Total_DUAS.xlsx` | EXPORTACION, EXPORTACION TEMPORAL, IMPORTACION DEFINITIVA, IMPORTACION TEMPORAL, PERFECCIONAMIENTO ACTIVO, REIMPORTACION, REIMPORTACION PERFECCIONAMIENTO PASIVO, TRANSITO y ZONA FRANCA |
| `Total_DUAS - Transito.xlsx` | TRANSITO |
| `Total_DUAS - Importacion.xlsx` | IMPORTACION DEFINITIVA, IMPORTACION TEMPORAL, REIMPORTACION y REIMPORTACION PERFECCIONAMIENTO PASIVO |

Se conservan los nombres, la columna única `NroDUA`, los ceros iniciales y la hoja
mensual, por ejemplo `marzo26`. Se eliminan duplicados dentro de cada archivo.
Un DUA de Tránsito/Importación también pertenece al Total: esto es intencional.
Una categoría vacía confirmada genera un Excel con encabezado, no deja un archivo viejo.
No se modificaron los otros bots.

## Originales por régimen

Se exportan desde los campos completos guardados en la base, con las mismas
columnas y orden del XML que los Excel antiguos: `aduana`, `ano`, `numero`,
`despacho`, `ingreso`, `declarante`, `bultos`, `modalidad`, `plazo`, `adu_destino`
y `ubi_destino` cuando aparece. Se conservaron texto, ceros iniciales, formato
General y encabezados en negrita, centrados y con bordes finos. Se verificaron
valores de muestra y estilos contra los archivos de referencia de los nueve
regímenes. Las hojas ahora llevan el mes y año: `septiembre26`, no `Sheet1`.

Solo hay dos formatos de entrega:

- **Dos partes:** `DUAS_SEPTIEMBRE_TRANSITO_1-15.xlsx` y
  `DUAS_SEPTIEMBRE_TRANSITO_16-30.xlsx`.
- **Mes entero:** `DUAS_SEPTIEMBRE_TRANSITO_2026.xlsx`, fusionado sin duplicados.

Los archivos se organizan en `<salida>/TRANSITO/2026-09/`, y de igual forma para
cada régimen. Esto conserva las carpetas con sus nombres y separa meses y años.
Los tres `Total_DUAS…xlsx` siguen directamente en la carpeta de salida.
Las fracciones de reintentos (1–7, 8–15, etc.) se reúnen internamente; nunca se
exportan como archivos adicionales. Una quincena pendiente no se exporta y un mes
solo se genera cuando está completo. La primera quincena completa puede exportarse
aunque aún falte la segunda. Un rango único 1–31 no se reparte por fechas inferidas:
para exportarlo en quincenas hacen falta consultas verificadas dentro de cada mitad.

Al cambiar entre las dos opciones, se reemplazan los originales de ese mes que
gestionó la app; la entrega anterior permanece en `entregas`. Archivos personales,
Excel antiguos no gestionados y otros períodos se conservan. El registro
`entregas/originales-AAAA-MM.json` identifica los archivos actuales y pendientes.

## Guardado y recuperación

- `data/duas.sqlite3`, junto al ejecutable o en la raíz del proyecto: consultas,
  sus estados, intentos, errores y registros completos extraídos del XML.
- Identidad de consulta: período `AAAA-MM`, régimen, día inicial y final. La base
  impide duplicar esa consulta y repetir un DUA dentro de su respuesta.
- El éxito del rango y sus datos se guardan juntos en una transacción. Un error
  de disco detiene el proceso y una consulta interrumpida puede retomarse.
- Cada navegación admite hasta 3 minutos para responder. Después, la espera del
  botón de descarga y la del XML completo admiten hasta 5 minutos cada una;
  continúan en cuanto se cumple su condición, sin consumir siempre ese tiempo.
  La comunicación con Edge admite 210 segundos por comando, superior al límite de
  navegación, para evitar el corte anterior a los 120 segundos.
- Cancelar se comprueba durante las esperas; una navegación activa puede tardar
  hasta su límite de 3 minutos. Cerrar espera al worker y al cierre del navegador.
- Los rangos personalizados pueden completar una quincena: 1–7 y 8–15 demuestran
  cobertura 1–15. Una consulta 1–31 no permite exportar solo 1–15, porque los datos
  almacenados no se filtran por una fecha individual cuya semántica no se ha verificado.
- Si se solicita actualizar un rango, un resultado anterior solapado no oculta su fallo.

## Descargas divididas automáticamente

Una descarga fallida de 1–15 se divide en 1–7 y 8–15. Para 16–30, las partes son
16–22 y 23–30; para 16–31, son 16–23 y 24–31. Se calcula el punto medio del rango
real, incluidos febrero y los años bisiestos. Cada parte que falla vuelve a
dividirse hasta llegar a un día. Los días individuales tienen como máximo tres
intentos por ejecución; después quedan pendientes para continuar otro día.

Las partes se consultan después de terminar la ronda actual. La app no divide
rangos cuando no puede iniciar Edge, al cancelar ni por un error al guardar en
disco. Los errores de descarga se muestran de forma breve y su detalle se conserva
en la consulta guardada.

La relación entre el rango original y sus partes se guarda de forma transaccional
en `query_parts`. Al reiniciar se recorren las partes pendientes, sin repetir las
completadas. Un rango dividido cuenta como completado solo cuando todas sus partes
lo están; el registro original conserva su historial de intentos. Para exportar se
usan las partes verificadas, se exige cobertura de todos los días y se eliminan
duplicados con la misma clasificación de siempre. Un solo día pendiente impide
publicar una entrega incompleta. No hace falta unir archivos intermedios.

**Volver a descargar rangos guardados** renueva también las partes de ese rango;
conserva la división conocida. Las bases anteriores se amplían automáticamente
al abrirse con esta versión, sin borrar descargas existentes.

## Publicación de los tres archivos

Primero se preparan los tres Excel desde los mismos datos verificados en
`<salida>/entregas/AAAA-MM/<identificador>/`. Después se actualizan los tres nombres
compatibles en la carpeta de salida y `ultima_entrega.json` registra el período,
rango, conteos y la carpeta de esa generación.

Cada archivo se reemplaza atómicamente. El conjunto de tres archivos **no es una
transacción atómica del sistema de archivos**: los consumidores deben esperar a
que la app anuncie la entrega completa. Se conservan las copias anteriores y un
diario de publicación; si hay un fallo se intenta restaurar el conjunto anterior.
Si se cerró abruptamente, la siguiente publicación recupera el diario antes de escribir.
Si Excel bloquea esa recuperación, cerrar el archivo y volver a unir. No se anuncia
éxito hasta completar la publicación.
Los originales se incluyen en esa misma recuperación al unir los tres archivos.
La exportación independiente de originales tiene su propia entrega recuperable.

Las generaciones históricas permiten recuperar entregas anteriores; no se borran
automáticamente. La base es local a la app, independiente de la carpeta de salida.
Respaldar `data/` con la app detenida conserva las descargas verificadas.

## Archivos anteriores

Los Excel antiguos se conservan. No se importan automáticamente como evidencia de
una descarga correcta: sus partes no siempre incluyen el año ni prueba del rango
consultado. La primera descarga en esta versión crea esa evidencia; a partir de
entonces se reanuda desde SQLite. Los Excel intermedios por régimen ya no son
necesarios para generar los tres archivos de entrega.

## Eficiencia y formulario

Se reutiliza un navegador durante las consultas exitosas y se reinicia si falla.
Se eliminaron las escrituras/lecturas de Excel intermedias y las pausas fijas del
calendario y de cinco segundos por régimen. Los 191 pares de `Names.xlsx` están en
`config/captcha_lookup.json`, cargados una sola vez. El Excel original se conserva
como referencia y para verificar la conversión, pero no es una dependencia de ejecución.

Se verifica que el calendario alcance el mes solicitado y se comprueban régimen,
ambas fechas y CAPTCHA inmediatamente antes de enviar. Un XML incompleto, una
respuesta inesperada o un identificador inválido dejan pendiente el rango; no se
usan archivos viejos para considerarlo completado. Una respuesta XML explícitamente
vacía es distinta de una consulta fallida.

## Pruebas y empaquetado

```powershell
python -m unittest discover -s tests -v
# Opcional: Edge real contra una página file:// local, nunca TICA:
$env:DUA_TEST_DRIVER = 'C:/ruta/a/un/msedgedriver-compatible.exe'
python -m unittest discover -s tests -v
python -m PyInstaller --distpath dist/AstraCode --workpath build/AstraCode ConsultaDUAs.spec
```

Las pruebas verifican clasificación exacta, quincenas, meses/años separados,
duplicados, cobertura, reintentos, rollback, cancelación, un cierre abrupto real,
publicación fallida, la interfaz y el formulario en un navegador local. También
verifican la subdivisión hasta días individuales, sus límites, reanudación,
actualización de partes y el tiempo de comunicación real usado por el controlador.
Las pruebas de originales cubren ambos modos, tipos y estilos, períodos aislados,
quincenas incompletas, cambio de modo, recuperación y los botones de la interfaz.
Para comparar con los archivos antiguos, definir `DUA_LEGACY_EXCEL` con la carpeta
de referencia que contiene los nueve regímenes y ejecutar las pruebas.
En Windows con Microsoft Excel y pywin32 instalados, definir `DUA_TEST_EXCEL=1`
para abrir los tres tipos de archivo final, un original y uno vacío con Excel
en carga normal (`CorruptLoad=0`), sin reparación ni extracción de datos.
También se valida el orden de los elementos de la hoja: `sheetPr`, `dimension`,
`sheetViews`. Leer un archivo con openpyxl no basta para asegurar compatibilidad
con Excel; el orden incorrecto de esos elementos causó el fallo de la primera
exportación de originales y está cubierto por la prueba de regresión.
Las pruebas de Edge se omiten si no está definida `DUA_TEST_DRIVER`.
Las pruebas de rutas cubren carpetas nuevas, rutas relativas, espacios, acentos,
escritura denegada y publicación/recuperación con rutas Windows de más de 260 caracteres.

Esta versión se validó sin consultas reales a TICA. No hay una medición que permita
prometer una aceleración específica del portal; se redujo el trabajo local repetido.
El ejecutable AstraCode se genera con otro nombre para conservar las versiones previas.

# Optimización de BLs_BOT — 6 de octubre de 2026

Rama: `AstraCode/bls-asyncio`. Este documento registra la migración original a
`v2/`. La organización actual usa `src/main.py`, `src/cli.py` y `src/core/`;
la carpeta `v2/` se eliminó y la distribución está en `dist/`. Las rutas `v2/`
mencionadas más abajo son referencias históricas a las verificaciones originales.
El código que generaba los ejecutables de `v2/dist` estaba en `src`; se organizó
en `v2`, archivando Selenium, herramientas antiguas y motor Playwright v5.1.
Se conservaron las modificaciones locales anteriores, datos, estados y ejecutables
durante esa migración. En la limpieza del 12 de octubre se retiraron esos motores
y ejecutables obsoletos. Las entradas, configuraciones y estados históricos están
ahora en `data/history/`; los registros históricos se conservan en `logs/`.
Este documento registra las mediciones de la migración; la organización vigente
se describe en [ARQUITECTURA.md](ARQUITECTURA.md).

## Protocolo observado y estrategia aplicada

El formulario público `hcgconocimientos.aspx` requiere el estado GeneXus del
navegador. El POST directo con un formulario HTTP fresco respondió 440; no se
adoptó como motor de búsqueda. Una consulta del navegador usa validación de
campos y un POST AJAX EENTER. El bot espera la inicialización de GeneXus,
termina la validación del BL y comprueba el POST real: BL y fechas exactos.
La tabla del DOM y su GXState pueden conservar datos anteriores después de AJAX;
se usa la respuesta confirmada `gxHiddens/Grid2ContainerDataV` y `gxGrids`.

Se compara la identidad completa de cinco partes, el BL literal y la secuencia.
Se conserva el enlace cifrado que TICA devuelve, sin reconstruirlo.
El GET de `hcglineas.aspx` con `BrowserContext.request` usa las mismas cookies y
contiene los valores completos de líneas en `Grid1ContainerDataV`, antes de
dibujar la tabla. Se valida identidad, BL, secuencia, esquema y cantidad.
El cuerpo original y la tabla dibujada coinciden en las páginas verificadas.
Todas las APIResponse HTTP se liberan con `dispose()`.

La opción predeterminada combina sesiones reutilizadas por trabajador y detalle
HTTP. El formulario conserva JavaScript; imágenes, fuentes, CSS y multimedia se
bloquean. Un trabajador no comparte su contexto ni sus campos con otro.
Se descarta el contexto tras errores, al cancelar, a los 100 usos o tras 600
segundos, entre consultas. Cada BL usa por defecto su mes de arribo como rango.
No hay una pausa fija por fila ni un corte total por duración del BL.

Una tabla vacía confirmada se guarda con cero filas. Una búsqueda sin la
identidad exacta queda pendiente, igual que errores o respuestas incompletas.
No se agregan ni eliminan ceros. Se conservan `013`, `001` y los números
decimales textuales (`191.000`) que el parser anterior podía convertir a números.
Las columnas de salida siguen siendo las 18 visibles más `manifiesto` y `bls`.
La limpieza histórica de comas/comillas se mantiene en los valores de líneas;
las identidades y el BL se agregan literalmente.

## SQLite y reanudación

La firma incluye la selección textual y su orden, hoja, URL y rango efectivo.
La concurrencia no cambia la firma. Cada lote tiene SQLite y CSV separados.
`inputs` conserva las filas de origen; `jobs` identifica manifiesto+secuencia+BL.
Las secuencias equivalentes 1/001 comparten clave, conservando el texto de entrada.
`runs`, `attempts` y `results` conservan la ejecución y el resultado.

Una reserva atómica entrega un token único. El resultado y Guardado se confirman
en la misma transacción; un token atrasado no puede guardar otro intento.
Un bloqueo del lote impide dos escritores y se adquiere antes de recuperar
Descargando como Pendiente. Fallos de disco detienen el motor; no se confunden
con fallos de red. Una ronda de trabajos queda congelada en una tabla temporal
SQLite y se recorre sin duplicar todos los payloads en una cola de memoria.

Los reintentos automáticos posteriores abarcan errores transitorios; una ausencia
confirmada o identidad incorrecta no se consulta repetidamente en esa misma
ejecución. Pulsar Iniciar otra vez vuelve a intentar todos los pendientes.
Las actualizaciones de Tk y del registro pasan por colas al hilo de la interfaz.
Los contadores durante la descarga se mantienen en memoria a partir de las
transacciones, evitando COUNT de todo el lote por cada BL. La exportación se hace
al finalizar/detener, ordenada por fila de entrada y posición de línea, mediante
un archivo temporal y reemplazo final.

## Comparación real acotada

Entrada: una muestra de `Bls_sin_courier_prueba.xlsx`, generado por Manifiestos.
La primera muestra tenía cuatro BL; dos devolvieron búsquedas vacías confirmadas
y permanecen pendientes. La comparación de rendimiento usa los mismos dos BL
que sí devuelven líneas, con ceros iniciales, en dos rondas de orden inverso.

| Estrategia | Ronda 1 | Ronda 2 | Resultado |
| --- | ---: | ---: | --- |
| Contexto nuevo y detalle navegador, 1 trabajador | 12,079 s | 39,583 s | En la segunda ronda hubo un timeout; 1/2 guardados |
| Contexto reutilizado y detalle navegador, 1 trabajador | 12,185 s | 9,845 s | 2/2 guardados en ambas rondas |
| Contexto reutilizado y detalle HTTP, 1 trabajador | 8,501 s | 8,129 s | 2/2 guardados en ambas rondas |
| Contexto reutilizado y detalle HTTP, 2 trabajadores | 6,831 s | 7,335 s | 2/2 guardados en ambas rondas |

Las estrategias completas produjeron CSV idénticos en todas las celdas.
La mediana pasó de 11,015 s con navegador reutilizado a 7,083 s con detalle HTTP
y dos trabajadores: aproximadamente 36% menos tiempo en esta muestra.
Con un trabajador, HTTP redujo solicitudes del navegador de 250/246 a 112/110,
más dos GET HTTP por ronda. Los contadores del navegador incluyen abortados;
no miden bytes ni representan todas las solicitudes internas del cliente HTTP.

Se eligieron dos trabajadores por defecto, configurables de 1 a 20. Dos BL y
dos rondas no acreditan capacidad mensual sostenida ni que 20 sea lo más rápido.
La prueba inicial con timeouts no se presenta como mejora de velocidad normal.
No se ejecutó la base anual ni se alteraron sus resultados de producción.

Evidencia local: `logs/optimizacion_20261006/comparacion_validada/comparacion.json`.
Comando reproducible, en una carpeta nueva para una comparación nueva:

```powershell
python scripts/benchmark_bls.py --archivo ruta/Bls_sin_courier_muestra.xlsx --limite 2 --salida logs/comparacion_nueva
```

La integración final repitió los dos BL con el motor aplicado: 2/2 guardados,
cero pendientes y cero filas inválidas. La reanudación se comprueba sin nuevas
consultas. Sus bases y CSV están en `logs/optimizacion_20261006/integracion_final`.

## Verificación y límites

20 pruebas offline cubren lectura de texto, fechas mixtas, identidad AJAX,
columnas/contadores/BL incorrectos, vacíos válidos, rollback, bloqueo, recuperación,
token atrasado, CSV bloqueado, orden, duplicados y funcionamiento de la GUI.
La simulación de 357 BL con 20 trabajadores termina con 330 guardados y 27
pendientes; reintenta solo 27 y finaliza con 357. Una tercera ejecución consulta
cero BL. También se comprueba cancelar consultas activas y mantener lo guardado.

Las páginas reales de líneas examinadas enviaron el grid completo, sin NEXT.
Si se detecta otra página de búsqueda/detalle aún no validada, el motor conserva
ese BL pendiente y no guarda una tabla parcial. Extender la paginación exige
observar y probar el estado AJAX de ese caso; no se inventan offsets o enlaces.
Los máximos de `state.json` no prueban éxitos individuales y no se migran
automáticamente. Se conservan como historial y SQLite controla las nuevas bases.

El ejecutable nuevo se verifica sin TICA: abre Chromium en una página local,
lee un Excel con un BL textual de más de 15 cifras y ceros, confirma SQLite y
reanuda sin repetir el trabajo. La verificación queda bajo `logs/`.

El ejecutable final `v2/dist/BLs_BOT_AstraCode.exe` pasó esta verificación:
`ready`, `chromium`, `sqlite_and_resume`, `excel_zeroes` y `frozen` son verdaderos.
Reporte: `logs/optimizacion_20261006/ejecutable/verificacion.json`.

## Corrección del bloqueo al detener y reanudar

El uso real con 440.016 BL mostró `database is locked` al reanudar después de
detener cerca de la fila 1005. Se reprodujo offline manteniendo una cola sin
consumir: `sqlite3.close()` no liberaba el archivo mientras el cursor permanecía
referenciado. Las pruebas iniciales habían agotado la cola y no cubrían este caso.

Ahora el almacén conserva y cierra explícitamente el cursor antes de reemplazar
la cola o cerrar la conexión. El motor también lo cierra al finalizar una ronda
detenida. El exportador de consola usa una conexión de solo lectura, una instantánea
y cierre explícito; no recupera trabajos ni adquiere el bloqueo del escritor.

Pasan 22 pruebas. La regresión conserva una cola sin consumir mientras verifica
un nuevo commit, y la prueba de detención deja 49 BL pendientes de 50 y reanuda
hasta confirmar los 50. El ejecutable verifica también el cierre con una cola viva.
No se borra ni reconstruye la base de producción.

Tras cerrar la app se verificó el lote `62636bd358ebe60a`: `quick_check=ok`,
bloqueo exclusivo disponible, 994 BL guardados, 439.022 pendientes y 3.359
filas de resultados. La comprobación del bloqueo se revirtió sin modificar datos.
El ejecutable corregido reemplazó el archivo en la misma ruta y pasó la prueba
local, incluida `sqlite_queue_released=true`. Reporte:
`logs/optimizacion_20261006/ejecutable/verificacion_bloqueo_corregido.json`.

## Instalación del navegador desde la app

`core/browser_runtime.py` abre Chromium y, solo ante el error específico de
ejecutable ausente, ejecuta `node.exe cli.js install chromium --no-progress`
con el driver incluido en el paquete Playwright del bot. No invoca el `.exe`
como si fuera Python ni depende de `pip` en la PC destino. Instala las revisiones
compatibles de Chromium y sus componentes, incluido el modo headless.

La descarga corre en el hilo de trabajo y comunica etapas a Tk mediante la cola
de eventos. La barra se anima durante la instalación sin alterar el porcentaje
de BL guardados. Se verifica el lanzamiento antes de reservar un BL.
El caché de Windows queda en `%LOCALAPPDATA%/ms-playwright`, fuera de la extracción
temporal de PyInstaller. Se respetan ubicaciones explícitas configuradas mediante
`PLAYWRIGHT_BROWSERS_PATH`.

Detener cancela el árbol del instalador que abrió la app. Hay un límite total de
15 minutos por instalación; los fallos muestran cómo reintentar con Iniciar.
`PLAYWRIGHT_SKIP_BROWSER_GC=1` evita que esta instalación elimine revisiones usadas
por otros bots. No se intenta reinstalar ante cualquier error de lanzamiento.

Pasan 34 pruebas: además de SQLite y las descargas, se verifican ausencia frente
a otros errores, instalador exitoso/fallido/cancelado, tiempo máximo, estado de la
GUI y conservación de confirmados, pendientes e intentos si falla o se detiene
la preparación del navegador.

La primera prueba real del ejecutable, con caché vacío, descargó Chromium,
FFmpeg, Headless Shell y Winldd y confirmó apertura, SQLite, ceros y reanudación.
Reporte: `logs/optimizacion_20261006/instalacion_automatica/verificacion_pc_nueva.json`.

## Cortes de Internet y reportes de revisión

Ante errores de transporte se verifican dos destinos HTTPS independientes de
TICA. Una respuesta HTTP, incluso 403/503, prueba conectividad; los problemas de
SSL u otros resultados inconclusos no justifican espera indefinida. Solo cuando
ambos destinos fallan por transporte se pausa la cola compartida, sin consumir
otro intento del BL en curso. La espera no tiene límite y comprueba cada 10 s,
con timeout de 5 s por destino. Detener cancela la espera y conserva pendientes.
No se cambia la conectividad real de Windows durante las pruebas.

Los trabajadores comparten una generación de reconexión: los fallos de consultas
que comenzaron antes del mismo corte esperan juntos, incluso si terminan después
de que otro trabajador confirmó el regreso de la conexión. Si el portal falla
con Internet disponible, conserva los reintentos limitados. La instalación
inicial de Chromium usa la misma protección ante cortes.

Al detener o finalizar se exportan `BLs_sin_lineas.csv` (vacíos confirmados) y
`BLs_pendientes.csv` (pendientes o inválidos, también no consultados), ordenados
por la fila original y conservando texto. Incluyen intentos y último error.
SQLite sigue siendo la fuente de progreso y las exportaciones son atómicas.

Pasan 42 pruebas, con cortes simultáneos en varios trabajadores, reanudación
sin consumir intentos adicionales, fallo de TICA con Internet disponible,
espera persistente hasta Detener, reporte de vacíos y pendientes y estado de Tk.

El ejecutable final pasó la verificación con Chromium existente sin descargar,
y también reparó por descarga real un caché de prueba sin Headless Shell. En ambos
casos verificó SQLite, liberación de cola, ceros, pausa/reanudación simulada y CSV
de revisión. Reportes `verificacion_final.json` y `verificacion_reparacion.json`
bajo `logs/optimizacion_20261006/instalacion_automatica/`.
Se reemplazó `v2/dist/BLs_BOT_AstraCode.exe` por el mismo binario verificado,
comprobando igualdad SHA256; la configuración y la base de producción se conservan.

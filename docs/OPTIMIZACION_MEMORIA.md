# Optimización de memoria de los motores — 2 de noviembre de 2026

Rama `feature/optimizar-memoria-motores`, creada desde `8f75fb9` en un worktree
separado, `C:/Proyectos/CHC_OPTIMIZACION_RAM`. La rama de uso
`feature/sharepoint-oauth2`, su código y su instancia abierta se conservan.
Los commits anteriores ya estaban publicados y se comprobó su igualdad con el
remoto antes de iniciar. Esta entrega no instala, integra ni despliega el cambio.

## Cambios y contratos conservados

1. `chc_runtime/numeric_runtime.py` limita a un hilo el cálculo interno de
   OpenBLAS, OpenMP, MKL, BLIS, Accelerate y NumExpr antes de cargar NumPy/pandas.
   Se aplica dentro de los workers DUA, Manifiestos/BLs y revisión TICA; los
   proveedores diarios heredan ese entorno. No cambia los trabajadores de
   descarga configurados por el usuario, los procesos independientes ni asyncio.
2. `batch_worker.py` permite leer catálogos, configuración, resúmenes y páginas
   SQLite sin cargar pandas ni Playwright. El primer comando que necesita el
   motor prepara sus extensiones **en el hilo principal**, antes de delegarlo.
   Esto conserva la protección contra bloqueos de imports nativos en Windows.
   El catálogo `bls_source` instala el adaptador de generación al construir una
   base, en lugar de cargarlo al consultar los meses disponibles.
3. Solo en **Conocimientos con navegador oculto**, una vez recibida la respuesta
   AJAX confirmada del listado se libera su página pesada. La sesión, cookies,
   contexto HTTP y respuesta confirmada permanecen disponibles. Una página vacía
   del mismo contexto permite que el mecanismo original renueve los enlaces.
   El navegador visible conserva el listado y los otros procedimientos mantienen
   sus recorridos originales.

No se modifican parsers copiados, columnas, texto, ceros, multiplicidad, filtros,
paginación, validación de identidad/EOF, transacciones, calendarios, intentos,
checkpoints ni política de CSV manual. Las 166 fuentes y recursos registrados
conservan sus hashes. La primera carga de un motor pesado pasa al primer comando
que lo necesita; no se anuncia como mejora del tiempo de extracción.

Los cuatro workers DUA siguen preparando sus datos al abrir el panel. No se
fusionan motores ni se introduce una descarga automática al navegar. La
optimización medida no implica que el consumo de todos los bots sea constante
o que las páginas de TICA tengan un tamaño máximo.

## Mediciones

Windows, Python 3.12, mismos entornos y mismo equipo; comparación contra `8f75fb9`.
Dos repeticiones finales por perfil, después de una exploración inicial de tres.
Los lectores muestrean únicamente la familia de cada proceso de pruebas y
comprueban fechas de creación para evitar confundir PID reutilizados de Windows.
No se altera la memoria ni el estado de procesos ajenos.

**Residente** es la suma de Working Set de los procesos de esa familia: puede
contar páginas compartidas más de una vez. **Comprometida** es Private Bytes y
no equivale a RAM física. Las cifras se expresan en MiB. Se conservan métricas,
tiempos y firmas en [el recibo resumido](benchmarks/memoria-2026-11-02.json).

| Perfil recién abierto | Residente antes → después | Comprometida antes → después |
| --- | ---: | ---: |
| Detalles | 96,59 → 95,84 | 423,16 → 69,70 |
| Tránsito | 89,85 → 89,19 | 416,14 → 62,84 |
| Talón | 89,82 → 89,09 | 416,20 → 62,64 |
| XMovimientos | 89,68 → 89,13 | 416,95 → 63,77 |
| Listado de Manifiestos | 81,77 → 34,92 | 408,21 → 16,82 |
| Conocimientos | 81,67 → 34,94 | 408,11 → 16,83 |
| DUAs por manifiesto | 81,73 → 34,84 | 408,22 → 16,71 |
| Movimientos | 81,49 → 34,78 | 407,86 → 16,67 |
| Contenedores | 81,53 → 34,86 | 407,88 → 16,77 |
| BLs | 84,76 → 34,90 | 409,40 → 16,80 |
| Generador de bases | 87,56 → 34,89 | 413,78 → 16,78 |
| Catálogo BLs, después de leer meses | 87,83 → 34,89 | 414,09 → 17,74 |

Importar NumPy/pandas en una prueba mínima pasó de aproximadamente 397 a 43 MiB
comprometidos; la memoria residente apenas cambió. No presentar esa diferencia
como 354 MiB de RAM física liberada por motor.

Un portal local con listado de **2.000 filas y seis trabajadores** confirmó los
mismos 12 registros finales: cinco manifiestos Guardado y uno inválido que quedó
pendiente deliberadamente. La firma de todas las filas fue idéntica:
`daa99111869a903c792e35f328036fe958c8cdea5a49e83488676b74972023a6`.

| Medida del listado grande | Antes | Después |
| --- | ---: | ---: |
| Residente estable tras confirmar el listado | 652,73 MiB | 416,02 MiB |
| Comprometida estable | 898,40 MiB | 308,71 MiB |
| Pico residente durante la carga | 652,73 MiB | 663,97 MiB |
| Tiempo de la prueba, incluida carga y pausa de medición | 2,405 s | 2,633 s |

La reducción estable medida es del **36,3 % residente** y **65,6 % comprometida**.
El pico inicial no disminuye: el listado completo debe llegar y validarse antes
de liberarlo. Son mediciones de una muestra sintética, no una predicción de cada
lote real. Con dos y cuatro hilos numéricos el mismo ensayo conservó la firma,
pero comprometió 340,41 y 405,60 MiB; un hilo mantiene el menor compromiso medido.

## Extracción real acotada

Autorizada explícitamente para esta rama. Se usaron dos DUAs distintos entre los
cuatro consumidores, una ronda por bot, un trabajador y almacenamiento temporal
independiente. Manifiestos se limitó a un día; los detalles a un manifiesto.
BLs recibió un solo conocimiento Courier N de esa extracción nueva, con su
secuencia exacta. No se consultaron colas SQLite operativas para probar cambios.

| Procedimiento | Filas confirmadas | Columnas públicas | Pendientes |
| --- | ---: | ---: | ---: |
| Detalles | 1 | 38 | 0 |
| Tránsito | 3 | 8 | 0 |
| Talón | 8 | 7 | 0 |
| XMovimientos | 2 | 6 | 0 |
| Listado de Manifiestos del día | 16 | 29 | 0 |
| Conocimientos del manifiesto | 135 | 15 | 0 |
| BLs | 1 | 20 | 0 |
| DUAs por manifiesto | 262 | 12 | 0 |
| Movimientos por manifiesto | 3 | 16 | 0 |
| Contenedores y mercancías, Marítimo | 200 | 19 | 0 |

Los CSV se solicitaron explícitamente después de confirmar SQLite. Los archivos
internos/públicos coincidieron por firma; ninguna exportación disparó SharePoint.
Los datos y las páginas temporales de las pruebas se retiraron al cerrar sus
procesos; se conservan recibos pequeños, sin incorporar información extraída a
Git. Una muestra acotada no prueba todas las respuestas futuras del portal.

## Recuperación, navegación y regresiones

Pasaron **114 pruebas automatizadas distintas**, más cinco repeticiones adicionales
de la búsqueda GET de BLs (119 ejecuciones en total), y las diez muestras reales.
Los cinco grupos finales de pruebas terminaron con código cero.

Las comprobaciones cubren los cuatro DUA, cinco procedimientos de Manifiestos,
generación y catálogo BLs, búsqueda GET/POST, paginación, reanudación desde
checkpoints, errores parciales, vacíos verificados, cancelación, selección de
meses, inicio mensual, conservación de SQLite y exportación exclusivamente manual.
`test_listing_memory.py` compara filas/estados completos al liberar o conservar
el listado, con renovación de enlaces y conservación de cookies.
`test_catalog_memory.py` exige poder leer el catálogo sin dependencias de cálculo
ni navegador y sin escribir datos.

Se corrigió una suposición del test de Tránsito, reproducida también en la rama
base: cuando los dos días cruzaban de mes comprobaba el pendiente en la tabla
activa del mes nuevo. Ahora compara estado/intentos/resultado en la tabla original
y la selecciona explícitamente para verificar su exportación acumulada. No se
cambió el calendario ni el motor para resolver esa prueba.

Otras dos expectativas anteriores, también reproducidas en la rama base, exigían
CSV automáticos en la recuperación BLs y en el supervisor DUA. Ahora comprueban
que no se generan durante la consulta y que una exportación manual posterior
contiene exclusivamente las filas confirmadas. El portal local BLs modela el
indicador GeneXus de petición activa hasta consumir su GET; anunciarlo ocioso
durante esa respuesta podía provocar una segunda búsqueda en el test. El cliente
de búsqueda y los parsers de BLs no se modificaron.

La app de esta rama se cargó fuera de pantalla, con las seis raíces temporales,
antes de documentar: seis módulos conectados, cero avisos QML. La revisión global
del panel conserva las capturas y comprobaciones geométricas en 1280×774,
1000×680 y 1000×600. La instancia del usuario permanece abierta en su rama actual.

## Repetir las mediciones

Desde el worktree de optimización, con sus entornos disponibles:

```powershell
workbench/.venv/Scripts/python.exe tools/benchmark_memory.py --code-root C:/Proyectos/CHC_AUTOMATIZACION_TICA --iterations 2 --output runtime/memory/antes.json
workbench/.venv/Scripts/python.exe tools/benchmark_memory.py --code-root C:/Proyectos/CHC_OPTIMIZACION_RAM --iterations 2 --output runtime/memory/despues.json
bots/manifiestos/.venv/Scripts/python.exe tools/benchmark_listing.py --code-root C:/Proyectos/CHC_OPTIMIZACION_RAM --output runtime/memory/listado.json
```

Por defecto solo usan portales locales y datos sintéticos. La modalidad `--live`
requiere una muestra privada explícita y solo permite una repetición; no se usa
en las pruebas rutinarias. Para comparar presupuestos numéricos se puede establecer
`CHC_NUMERIC_THREADS` entre 1 y 64 en el proceso de prueba. Un valor ausente o
inválido usa 1; no es la configuración de trabajadores de descarga de la interfaz.

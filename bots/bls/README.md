# BLs_BOT — asyncio, sesiones reutilizadas y SQLite

La aplicación activa está en `src/`, rama `AstraCode/bls-asyncio`.
Lee las bases XLSX o SQLite que genera Conocimientos en Manifiestos y conserva los BL,
secuencias y valores extraídos como texto, incluidos sus ceros iniciales.
Cada intento consulta el mismo BL: no se generan variantes con ceros añadidos.

La documentación completa de funcionamiento, tecnologías, formatos, estados,
configuración y mantenimiento está en el
[Manual del bot](docs/MANUAL_BLS_BOT.md).

## Instalación de desarrollo

Windows de 64 bits, Python 3.12 con Tkinter y acceso a Internet para instalar
dependencias y descargar Chromium la primera vez.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe run_bot.py
```

`requirements.txt` contiene las dependencias de ejecución; `requirements-dev.txt`
agrega PyInstaller para compilar. Las pruebas usan `unittest`, incluido en Python.
La aplicación crea `config.json` al guardar ajustes; `config.example.json`
documenta los valores predeterminados sin rutas personales. La configuración local
existente se conserva y queda fuera de Git.

## Abrir la aplicación

Desde la raíz del proyecto, con el entorno virtual:

```powershell
python run_bot.py
# También: python src/main.py
```

El único ejecutable de esta versión es `dist/BLs_BOT_AstraCode.exe`.

Al pulsar **Iniciar**, si falta la versión necesaria de Chromium, la aplicación
la descarga con el instalador incluido y verifica que abra antes de consultar BL.
La ventana muestra la preparación y el registro de descarga. No hace falta
instalar Python ni ejecutar comandos para usar el `.exe`.
Se necesita Internet para la primera descarga. **Detener** también cancela la
instalación; ante un fallo se puede reintentar con **Iniciar**, conservando SQLite.

Si se confirma un corte de Internet, los trabajadores comparten una pausa sin
límite de tiempo y comprueban la reconexión cada diez segundos. Al volver la
conexión se repite el BL interrumpido con la misma identidad y el mismo intento.
**Detener** sigue disponible. Un fallo de TICA, una tabla incompatible o una
verificación de Internet inconclusa conserva los reintentos limitados.

## Trasladar la aplicación y el progreso

1. Detener el proceso, esperar a que finalice y cerrar completamente la ventana.
2. Comprimir `dist` incluyendo `config.json`, `data/` y `output/` completos.
3. Extraer en una carpeta con permisos de escritura en otra PC Windows de 64 bits.
4. Abrir `BLs_BOT_AstraCode.exe` y pulsar **Iniciar** con la misma base y filtros.
   La base cargada se restaura desde `data/Datos_Cargados/` y SQLite conserva los
   BL confirmados. No pulsar **Nueva descarga** para continuar el lote existente.

Con la ruta de salida vacía se usa `output` junto al ejecutable. Si se había elegido
una ruta externa, incluir esa carpeta al trasladar y seleccionar su ubicación nueva.
No es necesario copiar `%LOCALAPPDATA%/ms-playwright`: si falta Chromium, el bot
lo descarga ahí para el usuario nuevo. Si se desea evitar esa descarga inicial,
se puede trasladar también el navegador. Los BL y datos extraídos conservan texto
y ceros; una consulta que quedó interrumpida sin confirmar se vuelve a intentar.

## Descargar BL

Al abrir, un panel de carga bloquea los controles hasta restaurar la base.
La restauración se ejecuta en segundo plano y usa una caché SQLite de texto,
sin volver a analizar el Excel en cada apertura. Si existe solamente el XLSX
anterior, se convierte una vez; se conserva el Excel y el progreso del lote.
La primera preparación de una base grande puede tardar más. Si falla, los
controles vuelven a habilitarse para seleccionar el Excel nuevamente.
El botón **Seleccionar base…** admite Excel `.xlsx` y las bases de entrada
SQLite exportadas por Conocimientos o las cachés internas (`.sqlite3`, `.sqlite` o `.db`). La lectura de cualquiera
de los formatos y el cambio de hoja también muestran el panel de carga y bloquean
los controles. Si el archivo falla, la selección anterior se conserva.

La caché de entrada `data/Datos_Cargados/<hoja>.sqlite3` contiene las filas
normalizadas. Es independiente de la base de progreso `<lote>/SQLite/bls.sqlite3`.
La restauración de la base de 440.016 filas se comprobó en 2,09 segundos desde
SQLite en esta PC; la primera preparación requirió leer y convertir el Excel.
Detalles y límites de la medición: [docs/ARRANQUE.md](docs/ARRANQUE.md).

1. Seleccionar el Excel `Bls_sin_courier` y la hoja **BLS**, la base SQLite
   exportada por Conocimientos (tabla **BLS**), o abrir la caché
   `data/Datos_Cargados/BLS.sqlite3` directamente. En SQLite se usa la hoja guardada.
   Los archivos SQLite exportados usan siempre BLS, aunque se renombre el archivo.
   XLSX y SQLite de la misma selección, orden y columnas recuperan el mismo lote;
   cambiar solo el formato no repite los BL guardados. Las bases de progreso
   no se pueden seleccionar como entrada.
2. Revisar la carpeta de resultados. Se usan **dos trabajadores** por defecto;
   se pueden configurar entre 1 y 20 antes de iniciar.
3. Dejar activada **Usar el mes de arribo de cada BL** para procesar bases de
   distintos meses o años sin ajustar fechas manualmente.
4. Pulsar **Iniciar**. La tabla muestra fila, BL original, estado, intentos,
   registros guardados y último error.
5. Después de detener o reiniciar, cargar la misma base y pulsar **Iniciar**:
   solo se consultan los BL pendientes. Los fallos del portal tienen reintentos
   acotados; los cortes de Internet confirmados esperan reconexión. Una búsqueda
   sin coincidencia se conserva pendiente para revisión.

La lista de la ventana muestra hasta 1000 trabajos; SQLite conserva la selección
completa. Una selección con pendientes o entradas inválidas no se anuncia completa.
**Nueva descarga** crea otro lote para volver a consultar y conserva el anterior.
Si Excel bloquea la exportación, cerrar ese CSV y pulsar **Iniciar** permite
exportar nuevamente lo guardado, sin repetir los BL confirmados.

## Resultados y progreso

```text
<carpeta elegida>/<hoja>/<identidad del lote>/
  SQLite/bls.sqlite3
  CSV/Duas_procesados_<hoja>.csv
  CSV/BLs_sin_lineas.csv
  CSV/BLs_pendientes.csv
```

SQLite confirma el resultado y el estado Guardado juntos. Los BL pendientes,
intentos, errores, selección original y resultados quedan en la base local.
El CSV conserva las 18 columnas visibles de líneas más `manifiesto` y `bls`;
su orden es el de las filas del Excel, seguido del orden de las líneas de TICA.
Las copias idénticas de una entrada comparten consulta y mantienen sus referencias.
Cambiar el contenido u orden de la selección, la hoja o los filtros relevantes
puede crear una identidad de lote diferente. Renombrar el archivo o cambiar
entre XLSX y SQLite equivalentes conserva la identidad.

Los índices históricos de `state.json` se conservan en `data/history/`, pero no se convierten
automáticamente en éxitos: el motor anterior también avanzaba después de fallos.
Los resultados y archivos históricos no se borran.

Al finalizar o detener se exportan los BL **confirmados sin líneas** y los
**pendientes/ inválidos**, con fila original, identidad, intentos, cantidad de
líneas y último error. Una búsqueda sin coincidencia aparece como pendiente,
no como vacío confirmado. Los pendientes con cero intentos aún no se consultaron.

## Consola y pruebas

```powershell
python run_cli.py --archivo ruta/Bls_sin_courier.xlsx --hoja BLS --limite 2 --concurrencia 2 --salida logs/mi_prueba
python run_cli.py --exportar-db ruta/SQLite/bls.sqlite3 --salida ruta/CSV/datos.csv
python run_cli.py --archivo ruta/Datos_Cargados/BLS.sqlite3 --limite 2 --salida logs/mi_prueba_sqlite
python run_cli.py --archivo ruta/Bls_sin_courier.sqlite3 --limite 2 --salida logs/mi_prueba_sqlite
python -m unittest discover -s tests -v
```

Para generar el ejecutable: `build.bat`, desde la raíz. Las dependencias de
`requirements-dev.txt` deben estar instaladas en el entorno de desarrollo.
Cerrar la aplicación antes de compilar. El empaquetado usa `build/` como carpeta
temporal y actualiza solamente el `.exe` de `dist/`, conservando configuración,
entradas y resultados. Chromium se instala al iniciar
una descarga cuando falta, tanto desde Python como desde el ejecutable.

Para verificar el ejecutable sin consultar TICA:

```powershell
.\dist\BLs_BOT_AstraCode.exe --verificar-instalacion logs/verificacion.json
```

El informe debe indicar `ready: true`. Esta comprobación puede descargar Chromium
si falta. Las pruebas de `tests/` usan sesiones simuladas y archivos temporales.

El protocolo, las mediciones, garantías y límites están en
[docs/OPTIMIZACION_20261006.md](docs/OPTIMIZACION_20261006.md).

## Organización

```text
BLs_BOT/
  run_bot.py                  # Lanzador de la interfaz
  run_cli.py                  # Lanzador de la consola
  config.example.json         # Ejemplo de configuración versionable
  build.bat                   # Compilación del ejecutable actual
  requirements.txt            # Dependencias de ejecución
  requirements-dev.txt        # Dependencias para desarrollo y compilación
  README.md                   # Instalación y uso
  AGENTS.md                   # Instrucciones para agentes y aviso al terminar
  CLAUDE.md                   # Contrato e instrucciones de mantenimiento
  src/                        # Única implementación actual
    main.py                   # Interfaz y carga de datos en segundo plano
    cli.py                    # Procesamiento y exportación por consola
    config_manager.py         # Configuración local
    data_reader.py            # Lectura textual del Excel
    input_cache.py            # Caché rápida de entradas en SQLite
    input_files.py            # Apertura de Excel o SQLite y selección de hoja
    paths.py                  # Rutas de escritura fuera de src
    core/                     # Motor asyncio, TICA y persistencia del progreso
  dist/                       # Distribución y progreso actual, fuera de Git
  tests/                      # Regresiones del motor, navegador, Internet y GUI
  scripts/                    # Benchmark acotado del motor actual
  docs/                       # Arquitectura, mantenimiento y mediciones
```

- `src/main.py`: interfaz y cola de eventos hacia Tk.
- `src/input_cache.py`: almacenamiento textual y reemplazo atómico de la entrada.
- `src/core/inputs.py`: validación textual y firma del lote.
- `src/core/store.py`: selección, reservas, resultados y exportación SQLite.
- `src/core/tica.py`, `tables.py`: formulario y respuestas verificadas de TICA.
- `src/core/engine.py`: trabajadores asyncio y cancelación.
- `src/cli.py`: procesamiento y exportación por consola.
- `src/core/browser_runtime.py`, `internet.py`: navegador y espera de reconexión.
- `src/core/self_test.py`: verificación local del ejecutable.
- `scripts/`: comparación acotada; resultados de pruebas en `logs/`, fuera de Git.

Las carpetas locales `.venv/`, `build/`, `logs/`, `data/`, `output/`, `tmp/` y
`dist/` están excluidas de Git. `config.json` también es local. En desarrollo,
configuración, entrada cargada y salida predeterminada están en la raíz. En la
distribución se encuentran junto al `.exe`, dentro de `dist/`.
Los motores Selenium y Playwright anteriores, lanzadores duplicados, herramientas
experimentales y ejecutables viejos se eliminaron. Los Excel, configuraciones,
estados y ajustes del IDE y Claude anteriores se preservaron en `data/history/`; sus
registros están en `logs/history/`. El manifiesto local con hashes está en
`logs/organization/preserved.json`. El historial de código confirmado sigue en Git.

El mapa del código y las reglas para mantener esta estructura están en
[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

La corrección del contrato con Conocimientos, los archivos modificados y las
pruebas entre repositorios están en
[docs/COMPATIBILIDAD_CONOCIMIENTOS_20261012.md](docs/COMPATIBILIDAD_CONOCIMIENTOS_20261012.md).

La estandarización eliminó `v2/`: la implementación actual está en `src/`,
y los archivos locales se trasladaron a la raíz conservando sus contenidos y
verificando sus hashes. El lote existente de la distribución está ahora en
`dist/output/`, con sus mismos CSV y SQLite.

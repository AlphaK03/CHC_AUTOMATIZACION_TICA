# Restauración rápida de bases grandes

La entrada cargada se conserva en una caché SQLite independiente del progreso.
La importación admite Excel, SQLite de Conocimientos y la caché SQLite del bot. El Excel se mantiene como respaldo
cuando se migra una caché anterior. No se necesitan dependencias adicionales.

La ventana muestra un panel de carga con indicador animado y bloquea botones,
pestañas y campos mientras un hilo restaura la base. El hilo de Tk procesa el
resultado mediante una cola, retira el panel y habilita los controles. Ante
errores se habilita la selección de otro Excel. Cerrar durante la preparación
espera a que termine el hilo, sin interrumpir la escritura de la caché.

## Archivos

| Archivo | Contenido |
| --- | --- |
| `data/Datos_Cargados/<hoja>.sqlite3` | Entrada validada: esquema, cantidad y filas textuales ordenadas |
| `data/Datos_Cargados/<hoja>.xlsx` | Caché anterior, conservada tras convertirla una vez |
| `output/<hoja>/<lote>/SQLite/bls.sqlite3` | Progreso, intentos y resultados confirmados de consultas |

En el ejecutable estas carpetas están dentro de `dist/`, junto al `.exe`.
Importar otro Excel reemplaza atómicamente la caché de entrada de esa hoja.
La lectura comprueba versión, esquema, cantidad y valores textuales. Una caché
dañada intenta recuperar el Excel; si no existe, permite seleccionar la base.
La conversión conserva ceros, orden y firma del lote; no modifica su progreso.

## Abrir cualquiera de los formatos

En la interfaz, **Seleccionar base…** permite elegir `.xlsx`, `.sqlite3`,
`.sqlite` o `.db`. Los Excel conservan su selector de hojas. Las nuevas bases
SQLite de caché guardan el nombre de hoja en sus metadatos, incluso si se renombra el
archivo. Los SQLite de Conocimientos tienen una única tabla BLS de cinco columnas
TEXT y su hoja lógica siempre es BLS. Para las cachés anteriores sin ese dato se usa el nombre del archivo.
La selección, lectura y cambio de hoja se realizan en segundo plano con el
panel de carga. Un error conserva la base anterior y vuelve a habilitar la app.

En consola:

```powershell
python run_cli.py --archivo ruta/base.xlsx --hoja BLS --salida logs/prueba_excel
python run_cli.py --archivo ruta/Datos_Cargados/BLS.sqlite3 --salida logs/prueba_sqlite
```

Para SQLite, `--hoja` es opcional: se usa la hoja de la base. Si se indica otra,
se rechaza para evitar cambiar la identidad del lote. Se admiten la tabla BLS
de Conocimientos y la caché interna; la base de progreso se abre con `--exportar-db` para exportar
resultados, no como selección de BL.

## Comprobación local del 12 de octubre de 2026

La aplicación instalada en `dist/BLs_BOT_AstraCode.exe` se abrió con la base
existente de **440.016 filas**. Se inspeccionaron el panel durante la carga y
la ventana lista, y se volvió a abrir normalmente para comprobar la caché.

| Operación | Tiempo de restauración |
| --- | ---: |
| Primera preparación: lectura del Excel y creación de la caché | 61,295 s |
| Segunda apertura: restauración desde SQLite | 2,090 s |
| Lectura independiente de la misma caché | 1,988 s |

Los tiempos se miden desde que comienza la restauración de la base; no incluyen
extracción de PyInstaller ni importación de módulos antes de crear la ventana.
La primera preparación incluye la conversión y no es una medición aislada del
lector de Excel. Son mediciones de esta PC y esta base, con caché del sistema.

La firma de la entrada restaurada coincidió exactamente con la del lote existente
`62636bd358ebe60a`. Se verificaron los hashes de los datos trasladados y la
integridad de la base de progreso (`quick_check=ok`). No se consultó TICA.

Pasaron 49 pruebas: motor, persistencia, reanudación, navegador, Internet,
lanzadores, caché textual, reemplazo fallido, recuperación de errores y bloqueo
de la GUI durante la carga. La verificación del ejecutable confirmó también
`input_cache=true`, ceros del Excel, Chromium, SQLite y reanudación.

Evidencia local, fuera de Git: `logs/organization/input_cache_measurement.json`,
`src_tests.txt`, `final_exe_verification.json`, `gui_loading.png`, `gui_final.png`
y `dist/logs/debug.log`.

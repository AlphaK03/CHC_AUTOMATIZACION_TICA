# Instrucciones de mantenimiento — BLs_BOT

## Versión activa

Rama: `AstraCode/bls-asyncio`. Las fuentes están en `src/` y `src/core/`.
Leer [README.md](README.md) y [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).
El registro técnico y sus límites están en
[docs/OPTIMIZACION_20261006.md](docs/OPTIMIZACION_20261006.md).
`src/` contiene la implementación actual trasladada desde la antigua `v2/`.
No recrear motores anteriores, carpetas de código por versión ni alias antiguos.

## Contrato

- Entrada: XLSX con hoja BLS o SQLite con tabla BLS, creados desde Conocimientos.
- Conservar BL y secuencia como texto, incluidos todos sus ceros.
- Cada intento consulta el mismo BL; nunca inferir, agregar ni quitar ceros.
- Leer la respuesta AJAX confirmada: GXState y DOM anteriores pueden estar obsoletos.
- Verificar manifiesto completo, BL, secuencia, esquema y cantidades.
- Mantener las 18 columnas visibles de líneas más `manifiesto` y `bls`.
- La consulta sin coincidencia y las respuestas inválidas permanecen pendientes.
- Una tabla vacía acreditada es Guardado con cero filas; nunca guardar un parcial.

## Motor y persistencia

`src/core/engine.py` usa asyncio y un Chromium compartido. Cada trabajador posee
su contexto y página. La búsqueda requiere el formulario GeneXus del navegador;
el detalle HTTP usa sus cookies y el enlace entregado por TICA. Se descarta el
contexto ante errores y se renueva entre consultas a los 100 usos o 600 segundos.
Concurrencia predeterminada: 2; configurable entre 1 y 20.

SQLite confirma datos y estado Guardado en una transacción, reserva por token
y bloquea el lote antes de recuperar interrupciones. Cerrar explícitamente el
cursor de la cola antes de reemplazarla o cerrar la conexión. La exportación
de consola abre una instantánea de solo lectura. Un fallo de disco detiene
el motor; un CSV bloqueado conserva los resultados confirmados.

Tk se actualiza solamente en el hilo principal mediante colas. Los trabajadores
y logging no llaman a widgets ni a `after` desde sus hilos. Nueva descarga crea
otro lote y preserva el anterior. No anunciar éxito completo si quedan pendientes.
Los cortes confirmados de Internet comparten una pausa cancelable; los fallos
de TICA y verificaciones inconclusas mantienen los reintentos limitados.

## Organización y comprobaciones

Las dependencias de ejecución están en `requirements.txt`; PyInstaller está en
`requirements-dev.txt`. La configuración personal `config.json` queda fuera
de Git y sus valores de referencia están en `config.example.json`.
Entradas, resultados, estados y registros locales no se versionan ni se eliminan
durante una limpieza de código. Los datos históricos están en `data/history/`.
La entrada validada se guarda en `data/Datos_Cargados/<hoja>.sqlite3` mediante
`src/input_cache.py`, independiente de SQLite del progreso. Preservar el texto,
orden y firma del lote al restaurarla. La carga inicial se ejecuta en un hilo;
solo la cola de eventos actualiza Tk y retira el panel que bloquea los controles.
Si falta la caché, convertir el Excel anterior una vez sin borrarlo. Recuperar
los controles ante fallos y esperar al hilo de carga antes de cerrar la aplicación.
GUI y CLI abren Excel y SQLite de entrada con `src/input_files.py`. Preservar la
hoja guardada en SQLite; no tratar la base de progreso como lista de entrada.
Desde 2026-10-12 también se lee la tabla BLS exportada por Conocimientos, distinta
de la caché interna metadata/input_rows. Leerla en modo solo lectura, ORDER BY
rowid, validar cinco columnas TEXT y normalizar con data_reader.prepare_bls,
igual que XLSX. Conservar los ID2/ID3/ID4 derivados y la firma del lote idénticos
entre formatos. La caché interna sigue funcionando y conserva las hojas antiguas.
La nota para la otra sesión de Codex y las pruebas están en
[docs/COMPATIBILIDAD_CONOCIMIENTOS_20261012.md](docs/COMPATIBILIDAD_CONOCIMIENTOS_20261012.md).
La selección manual y el cambio de hoja también usan el hilo de carga y el panel.
Ante una selección fallida se conservan la base, hoja y configuración anteriores.

```powershell
.\.venv\Scripts\python.exe run_bot.py
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe run_cli.py --archivo ruta/muestra.xlsx --hoja BLS --limite 2 --salida logs/prueba_nueva
.\.venv\Scripts\python.exe run_cli.py --exportar-db ruta/SQLite/bls.sqlite3 --salida ruta/CSV/datos.csv
```

Las pruebas reales deben ser explícitas, acotadas y en una carpeta independiente.
El benchmark admite máximo cuatro BL. No ejecutar una base anual para comprobar
una refactorización ni alterar resultados de producción. Las pruebas offline
usan archivos temporales y sesiones simuladas.

## Ejecutable

`build.bat`, en la raíz, genera el candidato en `build/release/` y actualiza
`dist/BLs_BOT_AstraCode.exe`. Cerrar la app antes de reemplazarlo. Conservar
configuración, entradas y resultados junto al ejecutable. Recompilar tras cambios
funcionales y verificar el resultado con `--verificar-instalacion <informe.json>`.
Esta verificación prueba Chromium, Excel textual, SQLite y reanudación sin TICA.
La app instala Chromium al iniciar cuando falta, usando el driver incluido.

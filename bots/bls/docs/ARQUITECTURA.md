# Código activo y mantenimiento

Para la explicación completa de uso, tecnologías, formatos y estados, consultar
el [Manual del bot](MANUAL_BLS_BOT.md).

La implementación activa está en `src/`, en la rama `AstraCode/bls-asyncio`.
`run_bot.py` inicia `src/main.py`; `run_cli.py` ejecuta `src/cli.py`.
Ambos usan `src/core/engine.py` directamente. Los lanzadores, pruebas y
herramientas agregan `src/` a su ruta de importación. En desarrollo, `APP_DIR`
resuelve la raíz para separar las fuentes de configuración, entradas y resultados.

## Responsabilidades

| Archivo dentro de `src/` | Responsabilidad |
| --- | --- |
| `main.py` | Interfaz Tk, selección/caché de Excel, configuración y eventos del trabajador |
| `config_manager.py` | Valores predeterminados y configuración personal junto a la aplicación |
| `data_reader.py` | Lectura textual de Excel y fechas de manifiesto |
| `input_cache.py` | Caché SQLite de filas normalizadas, textual, ordenada y atómica |
| `input_files.py` | Apertura de Excel o SQLite de entrada y selección de hoja |
| `paths.py` | Carpeta de escritura en desarrollo y junto al ejecutable congelado |
| `cli.py` | Descarga acotada o exportación de SQLite sin abrir la GUI |
| `core/inputs.py` | Identidades de entrada, validación, fechas y firma del lote |
| `core/engine.py` | Trabajadores asyncio, rondas, detención y exportaciones finales |
| `core/tica.py` | Sesión individual de navegador, búsqueda AJAX y detalle HTTP |
| `core/tables.py` | Verificación de identidad, esquema, cantidades y valores textuales |
| `core/store.py` | Bloqueo de escritor, reservas, transacciones SQLite y CSV atómicos |
| `core/browser_runtime.py` | Preparación, instalación y cancelación de Chromium |
| `core/internet.py` | Verificación independiente de conectividad y pausa compartida |
| `core/self_test.py` | Verificación local de navegador, Excel, SQLite y reanudación |

## Flujo

1. La GUI o CLI lee el Excel o la tabla BLS exportada desde Conocimientos,
   conservando BL y secuencia como texto. Ambos usan `data_reader.prepare_bls`
   para obtener las mismas fechas y columnas derivadas; la caché normalizada
   se lee directamente sin reinterpretar sus valores.
2. La firma de entrada, hoja y filtros determina la carpeta del lote.
3. SQLite recupera consultas interrumpidas y reserva cada trabajo por token.
4. Un Chromium compartido aloja un contexto privado por trabajador.
5. La búsqueda confirma BL, fechas, manifiesto y secuencia en la respuesta AJAX.
6. El detalle se obtiene con las cookies del mismo contexto y se valida completo.
7. Resultado y estado Guardado se confirman juntos. Al terminar se exportan CSV.

La GUI recibe eventos por colas y actualiza Tk únicamente desde su hilo principal.
Los cortes de Internet confirmados comparten una espera cancelable; los fallos
del portal conservan reintentos limitados. SQLite controla el progreso, sin
índices históricos de JSON ni funciones de compatibilidad con los motores retirados.

## Código y datos locales

Las fuentes, pruebas, documentación, benchmark y ejemplo de configuración se
versionan. Configuración personal, Excel, SQLite, CSV, logs, cachés y compilaciones
quedan fuera de Git. No agregar credenciales ni rutas de usuarios a archivos fuente.
En Python, las carpetas de ejecución se crean en la raíz; en el ejecutable se
escriben junto al `.exe`, salvo que se elija una carpeta de salida externa.

La limpieza inicial retiró `legacy/`, `src/`, `tools/`, pruebas de motores anteriores,
sondas experimentales y ejecutables v2/v3/v5.1. Las entradas, estados, configuración
y ajustes locales del IDE y Claude se trasladaron a `data/history/` verificando sus SHA256.
Se conservaron los logs históricos. La estandarización trasladó las fuentes,
configuración, datos, logs y distribución a la raíz y eliminó la carpeta `v2/`.
Las fuentes de la versión actual se organizaron en `src/`; los motores antiguos
que antes ocupaban esa carpeta se retiraron.
El progreso de la distribución permanece dentro de `dist/output/`, con la misma
estructura e identidad de lote. Las salidas externas conservan su configuración.
Los manifiestos locales de la migración están en `logs/organization/`.
No convertir índices antiguos en éxitos: no demuestran consultas confirmadas.

## Validación de cambios

Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe run_cli.py --help
.\build.bat
.\dist\BLs_BOT_AstraCode.exe --verificar-instalacion logs/verificacion.json
```

Cerrar la aplicación antes de reemplazar el ejecutable. La compilación genera
archivos temporales en `build/` y conserva `dist/config.json`, `data/`, `logs/`
y `output/`. Si el `.exe` está ocupado, el candidato queda en `build/release/`.
La verificación local no consulta TICA, aunque puede instalar Chromium si falta.
Las consultas reales y el benchmark requieren una muestra explícita, acotada y
una carpeta nueva; nunca usar una base de producción para probar la organización.

## Arranque y base cargada

El hilo principal crea la ventana y un panel de carga antes de leer la base.
Todos los controles y pestañas quedan deshabilitados. Un hilo independiente
restaura `data/Datos_Cargados/<hoja>.sqlite3` y devuelve el DataFrame por la cola.
El hilo principal retira el panel y habilita los controles al terminar o fallar.
Cerrar durante la carga espera a que el hilo concluya su operación.

La caché guarda el esquema, cantidad y filas normalizadas como listas JSON
textuales ordenadas en SQLite. No se vuelven a interpretar fechas ni números.
Se comprueba versión, esquema, tipos y cantidad al leer; la escritura usa un
temporal cerrado y reemplazo atómico. Una caché dañada intenta recuperar el Excel.
Si solo existe el XLSX anterior, se lee y convierte una vez sin eliminarlo.
Importar otra base reemplaza la caché de esa hoja; no cambia el progreso de lotes.

Esta base de entrada es independiente de `<lote>/SQLite/bls.sqlite3`: cambiar el
formato local no modifica las identidades ni convierte pendientes en confirmados.
La GUI y CLI permiten abrir ambos formatos mediante `input_files.py`. En SQLite,
los metadatos conservan la hoja original y evitan que renombrar una base nueva
cambie el lote. Las cachés anteriores infieren la hoja del nombre del archivo.
La GUI también bloquea los controles durante la selección y lectura manual;
una selección fallida conserva la entrada anterior. Los SQLite de progreso
se rechazan como entrada y se mantienen de solo lectura al exportar.

La salida SQLite de Conocimientos tiene una única tabla BLS con cinco columnas
TEXT. `input_files.py` la reconoce por ese contrato y lee ORDER BY rowid desde
una instantánea de solo lectura. No exige metadatos de la caché interna ni los
añade al archivo original. Su hoja lógica es siempre BLS. Los mismos datos y
orden en XLSX o SQLite tienen idéntica firma y recuperan el mismo progreso.
La comprobación entre ambos repositorios está documentada en
[COMPATIBILIDAD_CONOCIMIENTOS_20261012.md](COMPATIBILIDAD_CONOCIMIENTOS_20261012.md).

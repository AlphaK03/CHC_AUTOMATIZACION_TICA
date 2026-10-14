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
`Instalar_Workbench.bat`, `Instalar_Detalles.bat` e `Instalar_Transito.bat` (Python 3.12).

Alternativa en PowerShell:

```powershell
py -3.12 -m venv workbench/.venv
.\workbench\.venv\Scripts\python.exe -m pip install -r workbench/requirements.txt
.\workbench\.venv\Scripts\python.exe workbench/app.py
```

Se instala `PySide6-Essentials==6.12.0`, con los bindings y módulos Qt necesarios.
El panel no usa WebEngine ni un servidor web. Las dependencias del motor de
Detalles se instalan por separado en `bots/detalles/.venv/`.

## Detalles operativo

Seleccionar **Detalles** en el panel lateral. Permite importar Excel, conservar
tablas SQLite, consultar y retomar pendientes, detener, exportar CSV/TXT/JSON,
buscar e inspeccionar resultados, administrar filas y configurar el motor.
La tabla **Validación · 2 DUAs originales** contiene resultados de la prueba real
de esta entrega. Seleccionarla y abrir **Base de datos** para revisar sus campos.

El [manual de integración](../docs/INTEGRACION_DETALLES.md) documenta cada función,
los respaldos, las rutas propias y el acceso temporal a la interfaz clásica.
Consultar resultados guardados y exportarlos no realiza consultas a TICA.

Esta rama añade **Diario automático** en Modo: indicar Desde, pulsar Iniciar
automático y revisar Calendario. No requiere Excel y conserva Manual. En un
equipo nuevo ejecutar `Instalar_Base_Diaria.bat`. [Uso y límites](../docs/PILOTO_DETALLES_DIARIO.md).
`--daily` abre esa vista sin iniciar descargas.

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

En **Manifiestos**, elegir procedimiento, período y modalidad y pulsar **Iniciar
consulta**. Cada procedimiento conserva su historial y funciona independientemente.
Las opciones técnicas, importación de progreso SQLite y herramientas están en
**Más**. **Ver resultados** abre únicamente sus CSV de datos.

**Crear base para BLs** permite cargar meses de Conocimientos, seleccionar fuentes
y generar SQLite o Excel Courier=N. **Abrir base en BLs** prepara la entrada del bot;
las consultas empiezan al pulsar Iniciar. También se admiten entradas externas.

En **BLs → Desde Conocimientos**, **Elegir meses…** ofrece solamente descargas
terminadas de Marítimo/Aéreo. **Iniciar consulta** genera la base y ejecuta BLs.
No hay que elegir un archivo intermedio. Los rangos indican sus días disponibles.
[Uso, disponibilidad y recuperación](../docs/BLS_DESDE_CONOCIMIENTOS.md).

Instalación nueva: `Instalar_Manifiestos.bat` e `Instalar_BLs.bat`.
[Contratos, recuperación, rutas y alcance comprobado](../docs/INTEGRACION_MANIFIESTOS.md).

## Interfaz y demostraciones

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

## Pendientes

Integrar los otros cuatro motores, unificar servicios tras comprobar equivalencia,
incorporar generadores de bases y preparar distribución ejecutable. El estado y
la visión completa están en `docs/CONTEXTO_PROYECTO.md`.

# CHC Workbench — Automatización TICA

Repositorio modular para mantener BLs, Detalles, DUAs Tránsito, Talón y
XMovimientos en un solo lugar y, posteriormente, integrar los generadores de bases.

**Estado actual: Detalles y DUAs Tránsito operativos en QML; tres módulos en demostración.**
Detalles importa bases a SQLite, consulta TICA, retoma pendientes, administra tablas
y exporta con el motor actual. Esta rama añade **Diario automático**: base propia
sin Excel, calendario y acumulación mensual. Tránsito usa la misma infraestructura
con su extracción de líneas y base propia del régimen TRANSITO. BLs, Talón y
XMovimientos siguen en demo. [Uso y alcance de Tránsito](docs/INTEGRACION_TRANSITO.md).
Los regímenes sin movimientos no bloquean la base diaria: se aceptan como vacíos
solo con respuesta confirmada de TICA; los errores conservan el estado pendiente.

Para abrir: doble clic en **`Abrir_Workbench.bat`**. En un equipo nuevo ejecutar
primero `Instalar_Workbench.bat`, `Instalar_Detalles.bat` y `Instalar_Transito.bat`. Consultar el
[manual del Workbench](workbench/README.md) y la [integración de Detalles](docs/INTEGRACION_DETALLES.md).

Capturas del prototipo: [vista general oscura](docs/preview/workbench-dark.png),
[espacio de Detalles](docs/preview/workbench-detalles.png) y
[tema claro con barra contraída](docs/preview/workbench-light.png).
Vista operativa actual: [Detalles integrado](docs/preview/detalles-integrado.png).

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
del mes correspondiente. Detalles y Tránsito tienen integración diaria; Talón y XMovimientos
siguen pendientes. Consultar [uso y límites del piloto](docs/PILOTO_DETALLES_DIARIO.md)
y el [contrato completo](docs/AUTOMATIZACION_DIARIA.md).

El destino va más allá de un menú de ejecutables: motores con contratos comunes
de entrada, ejecución, detención, eventos y exportación, preservando validaciones,
esquemas, ceros iniciales y recuperación. El acceso inicial por procesos separados
será una transición técnica cuando se autorice integrar los motores.

**Tecnologías del panel:** Python + PySide6 + Qt Quick/QML. Python conserva lógica
y automatización; QML define pantallas y componentes. SQLite es la persistencia
local; Playwright es el motor activo de los cinco bots copiados. En uso normal,
Detalles y Tránsito ejecutan sus motores en procesos propios. `chc_runtime/`
comparte persistencia, protocolo y coordinación; los otros tres módulos son demos.
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

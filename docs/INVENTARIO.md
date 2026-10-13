# Inventario del código actual

Revisión por lectura local, 12 de octubre de 2026. Todos los bots tienen cambios
sin confirmar. Consultar los manifiestos para las ramas, commits y hashes exactos.

| ID | Origen relativo a `D:/CHC_CONSULTORES/Repositorios` | Raíz copiada | Entrada nueva | Motor activo observado |
| --- | --- | --- | --- | --- |
| bls | BLs_BOT | raíz | `bots/bls/run_bot.py` | `src/core/engine.py`, asyncio y Playwright |
| detalles | Detalles_BOT | raíz | `bots/detalles/src/main.py` | `src/core/playwright_processor.py` |
| duas_transito | DuasTransito BOT | v2 | `bots/duas_transito/src/main.py` | `src/core/playwright_processor.py` |
| talon | Talon_BOT | v2 | `bots/talon/src/main.py` | `src/core/playwright_processor.py` |
| xmovimientos | XMovimientos_BOT | v2 | `bots/xmovimientos/src/main.py` | `src/core/playwright_processor.py` |

El nombre físico de Tránsito contiene un espacio: `DuasTransito BOT`. El ID nuevo
evita depender de ese nombre. Las tres carpetas `v2` se aplanan al módulo; sus
`src/` anteriores de la raíz no se copian.

## Entradas y estado

| Módulo | Entrada actual | Persistencia observada | Recurso requerido |
| --- | --- | --- | --- |
| BLs | Hoja BLS en XLSX o tabla BLS en SQLite; también caché propia | SQLite de entrada y de resultados/lotes | No usa el catálogo Excel de CAPTCHA |
| Detalles | Hoja Excel con `NroDUA`, importada al catálogo local | SQLite por tabla; resultado y éxito transaccionales | `config/captcha_lookup.json` |
| Tránsito | Hoja Excel con `NroDUA` | Sesión JSON por índice y salidas CSV/TXT | `Names_TicaPortal.xlsx` de v2 |
| Talón | Hoja Excel con `NroDUA` | Sesión JSON por índice y salidas CSV/TXT | `Names_TicaPortal.xlsx` de v2 |
| XMovimientos | Hoja Excel con `NroDUA` | Sesión JSON por índice y salidas CSV/TXT | `Names_TicaPortal.xlsx` de v2 |

Contrato BLS de Conocimientos: `IDManifiesto`, `Secuencia Tica`, `BL original`,
`Fecha Manifiesto`, `Mes`, cinco columnas TEXT y tabla `BLS`. No confundirlo con
una base de progreso ni con las listas `NroDUA`.

BLs conserva 18 columnas de líneas más `manifiesto` y `bls`. Detalles conserva
38 columnas. Los campos particulares de Tránsito/Talón/XMovimientos se mantienen
en sus flows; la copia no transforma ni unifica esquemas de salida.

## Dependencias

- BLs trae requisitos fijados: pandas, openpyxl, beautifulsoup4, lxml y Playwright.
- Detalles trae rangos de beautifulsoup4, openpyxl, pandas, Playwright, Selenium y
  requests. Selenium permanece en fuentes de compatibilidad dentro de `src/`.
- Las tres raíces `v2` no tienen `requirements.txt`. Talón y XMovimientos tienen
  archivos fuera de `v2` que describen el motor anterior y omiten dependencias
  activas. No se usan como instalación de las copias nuevas.
- Se agrega `requirements.runtime.txt` para esos tres módulos a partir de sus
  imports activos: pandas, openpyxl, beautifulsoup4, requests y Playwright. Los
  valores coinciden con requisitos ya presentes en BLs/Detalles; falta comprobar
  instalación y ejecución, no son un lock de dependencias validado.
- Tkinter viene con la instalación de Python para Windows; no se usa el paquete
  antiguo `tk==0.1.0`. Los motores Selenium conservados dentro de `src/core/` no
  son el camino registrado y requerirían sus propias dependencias.

## Compatibilidad y deuda observada

Los cinco caminos de GUI activos importan Playwright. Algunos comentarios,
docstrings y documentos antiguos aún describen XMovimientos o Selenium en otros
bots. Se conservan como parte de la copia; manda el punto de entrada observado.

Los specs de Tránsito, Talón y XMovimientos tienen rutas absolutas a los proyectos
originales y referencias internas de Playwright que requieren revisión. Se
preservan en `docs/reference` y no son una receta de compilación del monorepo.
El spec de Detalles resuelve desde `SPECPATH`; BLs usa un `build.bat` relativo.

Dentro de `src/` pueden permanecer procesadores Selenium históricos. Se conservan
para no podar arbitrariamente archivos del árbol activo; el registro apunta al
motor usado por la GUI. No se copia `Detalles_BOT/codigo viejo/`, ni los árboles
antiguos de las tres aplicaciones v2, ni separadores externos de versiones previas.

## Generador futuro: DUAS_SCRAPPING

Origen inspeccionado: `D:/PortafolioDesarrollador/DUAS_SCRAPPING`.

- Entrada: año, mes, régimen y rango de días.
- Motor actual: Selenium y Edge con driver configurado.
- Guarda consultas verificadas y registros completos en `data/duas.sqlite3`.
- Resuelve CAPTCHA con `config/captcha_lookup.json`; `Names.xlsx` es referencia.
- Exporta `Total_DUAS.xlsx`, `Total_DUAS - Transito.xlsx` y
  `Total_DUAS - Importacion.xlsx`, con `NroDUA` y hoja mensual.
- Acredita cobertura y separa períodos; ofrece subdivisión y reanudación de rangos.
- También exporta originales por régimen y entregas recuperables.

Su README actual refleja mejoras que el análisis histórico de Detalles del 3 de
octubre todavía no contiene. Ese análisis no debe tratarse como estado actual.
No se copia el generador en esta entrega: corresponde a integración posterior.

La fuente BLS de Conocimientos/Manifiestos y otros generadores quedan por
inventariar. La independencia completa de bases todavía no está implementada.

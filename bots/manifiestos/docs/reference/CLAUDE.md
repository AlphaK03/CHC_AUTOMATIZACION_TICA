# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current AstraCode guidance (2026-10-06)

BLS UI update 2026-10-12: compact screen-sized window, one main Meses tab and
an Archivos y opciones tab for source details/input-format/history. The output
format/path and generation actions live in a fixed footer outside the resizing
tables. Preserve staged loading and selection guards; scrolling table content
must not hide the Generate button. Month labels use Spanish names and full year.

BLS update 2026-10-12: default_roots includes only current public Knowledge CSVs
and private Knowledge SQLite. The UI presents one "Datos de esta app" origin;
external folders are a separate selection. Old src/output_manifest* roots are
not added automatically. Base output now supports .xlsx and .sqlite3/.sqlite/.db
through the same filtering/deduplication pipeline. SQLite publishes only table
BLS with five TEXT NOT NULL columns, inserted in XLSX order; query ORDER BY rowid.
Audit stays private and separate. Both exporters publish atomically, preserve
prior output on cancellation/failure, and retain leading zeros. Generated bases
remain in bases_bls; resultados remains CSV-only. Output controls/dialogs match
the chosen format. The BLs_BOT reader in its separate repository now accepts
the exported BLS table as well as XLSX and internal metadata/input_rows caches.
Both generated formats share normalization, text, order and batch signature;
same-input cross-format resume does not repeat saved BLs. Read the handoff note
BLs_BOT/docs/COMPATIBILIDAD_CONOCIMIENTOS_20261012.md before changing that contract.

Update 2026-10-12: BLS opens with a filename-only catalog, never a full data scan.
Choose year/month/mode and format before "Cargar datos elegidos". Current SQLite
is preferred; exported CSV companions and histories are skipped by default.
External mixed files are verified by their actual rows, not filtered blindly
by filenames. Catalog and loading use the Tk event queue; SQLite inspection is
cancelable via a progress handler and counts rows only once. Changing scope to
unloaded files disables generation until loading them. The CLI mirrors this
selection and adds --listar, --formato, --incluir-historicos. Read docs/BASES_BLS.md.

Update 2026-10-11: public CSVs now share resultados/<flow>/<year>/<mode>/ across
months within each bot, named e.g. conocimientos_maritimo_enero26.csv. SQLite progress
is private in datos_app/SQLite/<flow>/<year>/<mode>/ with its original numeric
filename. Adjacent relative export-location JSON keeps manual exports portable.
GUI startup and period runners migrate old paths under output locks, defer active
periods, preserve bytes/checkpoints, and never overwrite historical CSVs. BLS
source detection supports both layouts; generated XLSX goes to bases_bls and
audit databases to datos_app/bases_bls/auditoria. Read
[docs/ORGANIZACION_RESULTADOS_20261011.md](docs/ORGANIZACION_RESULTADOS_20261011.md).
Explicit cleanup in limpiar_resultados.py removes identical CSV copies and
fully covered historical versions, respecting row multiplicity and leading zeros.
It preserves unique history and all SQLite progress, defers active periods,
and writes a deletion audit. Never deduplicate legitimate extracted rows.
Failure CSV variants (fallidos, fallidas, excluidas) from the current bot
live under resultados/<flow>/<year>/<mode>/fallidos/. Normal data CSVs
stay in the mode directory. Use csv_directory, failure_csv_path and
exclusion_csv_path consistently; DUAs manual exports create the failure folder.
Unique historical CSVs now live in <mode>/historicos/, with historical failures
in <mode>/historicos/fallidos/. Preserve their filenames and bytes; csv_directory
accepts historical=True and migration retains this separation on restart.

Update 2026-10-10: DUAs and Movimientos use an isolated Playwright HTTP context
per manifest, copying browser cookies except ASP.NET_SessionId and preserving
GX/access cookies and User-Agent. DUAs downloads have no operation/total timeout;
one HTTP attempt per page; non-200 or invalid content remains pending and the
worker continues, except the recognized frmAmbiente error form for hcgduama.aspx:
it becomes terminal Excluido and is never automatically retried. DUAs exports
normal data plus duas_excluidas_<mode>_<month-name><year-short>.csv in fallidos/.
Existing jobs schemas migrate transactionally after acquiring the output lock.
Waiting activity appears every 15 seconds; Stop cancels safely.
DUAs int-conversion errors (invalid literal for int() with base 10) remain
retryable. At start_run, obsolete conversion-only Excluido jobs without saved
data are returned to Pendiente with job_reconsiderations audit; actual frmAmbiente
exclusions and saved jobs are preserved. A starred grid counter may be treated
as overflow only when the row count exceeds its width and another numeric
counter matches all DataV rows; identifiers and leading zeros stay unchanged.
DUAs also accepts nRC signed-16 wrap only when numeric Count equals DataV length
and nRC equals (length + 32768) % 65536 - 32768; e.g. 61356 rows -> -4180.
Identity/schema/width/EOF checks still apply; mismatches remain Pendiente.
Main-form navigation and the other flows retain their limits. Read
[docs/DUAS_SESIONES_Y_ESPERA_20261010.md](docs/DUAS_SESIONES_Y_ESPERA_20261010.md).

Read [RESULTADOS_Y_FLUJOS_ASTRACODE.md](RESULTADOS_Y_FLUJOS_ASTRACODE.md) and
[docs/GUIA_REPLICACION_BOTS.md](docs/GUIA_REPLICACION_BOTS.md) first. They describe
the active Conocimientos, DUAs and Movimientos paths and supersede the legacy
sub-page, CSV resume and failure-export descriptions below for those flows.
Keep the replication guide synchronized with its identical copy in Detalles_BOT.

- These three flows use HTTP requests with Playwright session cookies, bounded
  asyncio workers, persistent SQLite jobs/results, and the shared progress panel.
- Preserve that panel and its main-thread Tk updates. Configure concurrency before
  starting: 1–32; defaults 32 for Conocimientos and 4 for DUAs/Movimientos.
- Active orchestration: `conocimientos_flow.py` and `tablas_flow.py`. Protocol and
  persistence: `conocimientos.py`, `conocimientos_queue.py`, `tablas_manifiesto.py`.
- Acquire the output lock before recovery or processing. Commit validated data and
  success together. Resume pending jobs, never from a maximum CSV row index.
- Conocimientos preserves page checkpoints; refreshing verifies the first page and
  last saved anchor before continuing. Do not turn partial data into success.
- Preserve original columns, legitimate duplicate rows, and output order. A valid
  empty table is a completed job; an invalid response is not an empty result.
- Export only data CSV for Conocimientos/Movimientos; DUAs also exports its
  terminal frmAmbiente exclusions (origin row, manifest, date, reason, attempts).
  Keep ordinary pending/control/error data in SQLite.
  `resultados.py` resolves separate public bot/year/mode and private progress paths.
- Do not automatically apply concurrency to Tabla principal or Contenedores.
- Keep test databases and live probe outputs separate from production. Tests below
  are offline; live tests must be explicit and bounded.
- The separate "Crear base para BLs_BOT" section is a local-data workflow:
  `bls_base.py`, `bls_base_panel.py`, `bls_base_cli.py`. Read
  [docs/BASES_BLS.md](docs/BASES_BLS.md) before modifying it. It consumes only
  confirmed SQLite rows or compatible local CSV/XLSX, filters Courier=N, exports
  four original input columns plus Mes, and preserves identifier text. Recover
  numeric XLSX padding only from explicit zero formats; never guess lost digits.
  Deduplicate identical manifest+sequence+BL; exclude conflicting BL for the same
  manifest+sequence with an internal audit. Preserve download progress windows.

## Running the project

All scripts must be run from `src/` as the working directory, or with `src/` on `PYTHONPATH`, because imports are relative (e.g. `from utils import load_config`).

```bash
# Launch the main GUI bot
cd src && python manifest_gui.py

# Launch the standalone CSV splitter utility
cd src && python dividir_csv.py
```

Offline checks from the repository root (PowerShell):

```powershell
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
```

There is no required build step for the Python GUI.

## Dependencies

Install into the `.venv` virtual environment:

```bash
pip install -r requirements.txt
playwright install chromium
```

The scraper runs Playwright's **Chromium** (not Edge). There is no external driver binary needed — Playwright manages the browser itself.

## Configuration

`config/config.json` is the single config file. Key fields:

| Field | Description |
|---|---|
| `timeout_manifest` | Playwright wait timeout in seconds (default 120) |
| `headless` | `true` to run browser headlessly (default `false`) |
| `output_manifest_folder` | Output dir for "tabla" CSV flow |
| `log_file` | Log path for the tabla flow (relative to `src/`) |

Flow-specific log file keys: `log_file_duas`, `log_file_movimientos`, `log_file_conocimientos`, `log_file_contenedores`. Output folder keys follow the pattern `output_manifest_<flow>_folder` (e.g. `output_manifest_duas_folder`); if omitted, defaults to a folder named `output_manifest_<flow>` inside `src/`.

UI preferences (last-used month/year/modes/flow) are persisted in `src/manifest_prefs.json` at runtime.

## Architecture

The following describes the original browser paths. For the three tracked
AstraCode flows, use the current guidance and linked documents above.

### Entry points

- **`manifest_gui.py`** — Tkinter GUI. Reads/writes `manifest_prefs.json`, lets the user pick transport mode(s) (marítimo/aéreo/terrestre), month/year, and scraping flow, then calls `asyncio.run(run_manifest_*_bot(...))` from `manifest_scraper.py`. The GUI blocks the main thread while the async bot runs.
- **`dividir_csv.py`** — Standalone Tkinter tool that splits a large CSV into parts that fit within Excel's 1,048,576-row sheet limit.

### Core scraping (`manifest_scraper.py`)

All scraping uses **Playwright async API**. The module-level `run_manifest_*_bot()` functions are async coroutines that each:
1. Launch a single Playwright Chromium browser.
2. Instantiate one `ManifestScraper` per transport mode and call `run_*_for_mode()`.
3. Close the browser when done.

`ManifestScraper` is constructed with `(config, browser)` and reuses the same browser across calls. All scraping targets:  
`https://portaltica.hacienda.go.cr/ticaexterno/hcicgmic.aspx`

#### Browser/context pattern

- `open_page()` opens the main results page as `self.page`.
- Each sub-page (DUA, movimiento, conocimiento, contenedor) is opened in its own `BrowserContext` via `_open_sub_page(href)`, then the context is closed immediately after processing. This prevents navigation in a sub-page from affecting `self.page`.
- Static assets (CSS, fonts) are blocked on every page via `_block_static()` to reduce load time.

#### Hidden grid extraction

The site stores grid data in a hidden `<input name="Grid1ContainerDataV">` as a JSON array of arrays. The scraper reads this with `_read_hidden_grid()` rather than parsing visible DOM rows, making extraction faster and more reliable. `_read_hidden_grid_stable()` polls until the value is stable across multiple reads (used before pagination clicks).

#### The five flows

| Flow key | Run function | Index column | Notes |
|---|---|---|---|
| `tabla` | `run_manifest_bot()` | — | Extracts visible DOM rows from main table |
| `duas` | `run_manifest_duas_bot()` | `index_flujo_duas` | Navigates to `hcgduama.aspx` per row |
| `movimientos` | `run_manifest_movimientos_bot()` | `index_flujo_movimientos` | Navigates to links matching `*mov*` per row |
| `conocimientos` | `run_manifest_conocimientos_bot()` | — (uses `_append_df_to_csv`) | Navigates to `hcgcons.aspx` per row; handles multi-page results via `span.PagingButtonsNext` |
| `contenedores` | `run_manifest_contenedores_bot()` | `index_flujo_contenedores` | Three-level nesting: main → `hcgkonte.aspx` → `hcgkonli.aspx` for merchandise per container |

All flows except `tabla` write a `*_fallidos_*.csv` alongside the main output to capture unprocessable rows.

**Resume logic:** `init_*_output()` reads the maximum value of the flow's index column from any existing CSV and skips rows up to that index, allowing interrupted runs to resume. The `conocimientos` flow does not use an index column and instead appends directly.

**Link snapshot pattern:** Before iterating rows, `_snapshot_main_table_links()` pre-reads all hrefs and row metadata from `self.page` into a plain Python list. This avoids stale Playwright element handles after sub-page navigation.

### Utilities (`utils.py`)

- `load_config()` / `save_config()` — read/write `config/config.json` (resolved two directory levels above `src/`, i.e. the repo root).
- `setup_logging(log_file)` — configures `logging` to write to both a file and stdout. Creates the `logs/` directory if absent. **Must be called before the first log message in each bot function.**

### Transport mode mapping

The site uses numeric values for the `vVTRANS` select element:

| Mode key | Site value |
|---|---|
| `maritimo` | `"1"` |
| `aereo` | `"4"` |
| `terrestre` | `"7"` |

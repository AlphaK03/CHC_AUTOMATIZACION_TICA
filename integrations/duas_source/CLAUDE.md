# Repository guidance — Consulta DUAs / AstraCode

Read [README.md](README.md) for the active architecture, output contracts and limits.

- Entry point: `python src/main.py`; Tk worker notifications go through a queue.
- `src/tica_dua_bot.py`: Selenium Edge, validated calendar dates and complete XML.
- `src/runner.py`: fair rounds of unresolved leaves, persistent bisection after a
  failed download, down to single days (three attempts per day per invocation).
  Browser launch failures retry without splitting; storage failures remain fatal.
- `src/data_store.py`: local SQLite at `data/duas.sqlite3`, range coverage and classification.
- `src/exports.py`: stage all three workbooks, retain generations, publish compatibility
  names with per-file atomic replacement and a recoverable journal. The three-file
  set is not filesystem-atomic: consumers must wait for completion.
- CAPTCHA lookup: immutable cached `config/captcha_lookup.json`; `Names.xlsx` is
  only the historical conversion reference, not an active dependency.
- The nine REGIMENES and four REGIMENES_IMPORTACION are compatibility requirements.
  Do not change classifications or output names without explicit user direction.
- All three output workbooks have a single textual `NroDUA` column and a monthly
  sheet such as `marzo26`. Transit/import entries intentionally also appear in Total.
- Original exports preserve XML fields and legacy Excel styles, with monthly
  sheets, under `<output>/<REGIMEN>/YYYY-MM/`. Exactly two modes: two complete
  half-months or one complete month. Never expose retry fragments as Excel files.
  `original_exports.py` stages them; `excel_format.py` writes literal text and
  worksheet dimensions. Standalone originals may export completed halves while
  others remain pending; the three totals still require every regime complete.
- Publication journals cover dynamic nested original paths and removals of prior
  app-managed files. Validate paths and preserve old generations during recovery.
- Use `output_paths.filesystem_path` for Windows export I/O, including staging,
  backups and recovery, so long paths work with LongPathsEnabled=0. Use display
  paths in returned filenames/UI; keep relative output settings anchored to the app.
- Never mark success because an older Excel exists. Never infer full-month coverage
  from the workbook name or DUA year. Legacy files are not automatically trusted.
- Hold RunLock before planning, downloading or collecting a database. Respect the
  separate publication lock for output-folder recovery and publication.
- Storage errors are fatal; preserve pending work rather than treating them as
  portal failures. A malformed or incomplete response is not an empty success.
- `query_parts` links a failed parent to two strictly smaller, adjacent children.
  Completion uses the current leaves, not a split parent's historical status or
  records. Export ignores split parents and verifies every day via their leaves.
  Refresh must invalidate contained saved parts, and resume must reuse successes.
- Tests are offline: `python -m unittest discover -s tests -v`. Optional real Edge
  tests require DUA_TEST_DRIVER and navigate only to the local file fixture.
- For export changes, check SpreadsheetML element order and run DUA_TEST_EXCEL=1
  with installed Excel/pywin32 when available. openpyxl accepts incorrectly ordered
  worksheet XML that Excel rejects. Dimension belongs after sheetPr, before
  sheetViews; actual Excel tests must use normal load, never repair/extract mode.
- Default driver is app-local `drivers/msedgedriver.exe`. Respect explicit saved
  paths. Do not silently update shared drivers belonging to other bots.
- Package with `ConsultaDUAs.spec`; do not commit generated data, drivers or binaries.
- GitHub account: AlphaK03. Keep work on the requested feature branch.

"""
main.py  —  BLs BOT · asyncio
CHC Consultores  |  Interfaz mejorada para usuarios no técnicos.

Two-tab Tkinter interface:
  Tab 1 "Procesamiento": file selection, progress bar, activity log, start/stop.
  Tab 2 "Configuración": all settings (no JSON editing required), save button.
"""

import os
import sys
import logging
import threading
import queue
import time
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext

from config_manager import load_config, save_config
from paths import APP_DIR
from data_reader import leer_bls
from core.engine import BLSProcessor
from input_cache import load_input_cache, save_input_cache
from input_files import input_sheets, load_input_file


# ── Log area colour scheme ─────────────────────────────────────────────────────
# All colours are chosen for readability on the dark (#1e1e1e) log background.

_LOG_COLOURS = {
    "error":     "#f44747",   # bright red
    "warning":   "#e0a050",   # warm amber / orange
    "success":   "#4ec9b0",   # teal green  — data saved, operation complete
    "highlight": "#9cdcfe",   # light blue  — significant event found/detected
    "default":   "#d4d4d4",   # light grey  — ordinary informational messages
}

# Substrings (lower-case) that promote an INFO message to green "success".
# Applied only after confirming the record is INFO level, so error messages
# containing similar words are never misclassified.
_SUCCESS_WORDS = (
    "guardado",                # CSV row saved
    "extraídos correctamente", # detail data fully extracted
    "detalle extraído",        # N rows pulled from detail table
    "restaurados desde",       # cache restored on startup
    "cargada",                 # sheet loaded successfully
    "proceso completado",      # full run finished
    "configuración guardada",  # user saved settings
)

# Substrings that promote an INFO message to blue "highlight".
_HIGHLIGHT_WORDS = (
    "coincidencia exacta",         # exact BL + manifest match found
    "tabla principal encontrada",  # main results table appeared
    "tabla de detalle encontrada", # detail table appeared
    "campos encontrados",          # form fields ready for input
    "chromium compartido iniciado", # browser session established
    "iniciando procesamiento",     # user pressed Start
)


# ── Logging handler that writes to the GUI log area ───────────────────────────

class _TextHandler(logging.Handler):
    """
    Routes log records through a queue consumed by the Tk main thread.
    Each record is tagged with a colour based on its level and content.
    """

    def __init__(self, widget: scrolledtext.ScrolledText):
        super().__init__()
        self.widget = widget
        self.events = queue.Queue()
        self._init_tags()
        self.poll_id = self.widget.after(100, self._poll)

    def _init_tags(self):
        """Configure named colour tags on the widget (called once in main thread)."""
        for name, colour in _LOG_COLOURS.items():
            self.widget.tag_configure(name, foreground=colour)

    def _classify(self, levelno: int, raw_msg: str) -> str:
        """Return the tag name for a record based on level, then keywords."""
        if levelno >= logging.ERROR:
            return "error"
        if levelno >= logging.WARNING:
            return "warning"
        if levelno == logging.INFO:
            low = raw_msg.lower()
            if any(kw in low for kw in _SUCCESS_WORDS):
                return "success"
            if any(kw in low for kw in _HIGHLIGHT_WORDS):
                return "highlight"
        return "default"

    def emit(self, record: logging.LogRecord):
        msg = self.format(record) + "\n"
        tag = self._classify(record.levelno, record.getMessage())
        self.events.put((msg, tag))

    def _poll(self):
        for _ in range(200):
            try:
                msg, tag = self.events.get_nowait()
            except queue.Empty:
                break
            self._append(msg, tag)
        self.poll_id = self.widget.after(100, self._poll)

    def close(self):
        try:
            self.widget.after_cancel(self.poll_id)
        except tk.TclError:
            pass
        super().close()

    def _append(self, msg: str, tag: str):
        self.widget.configure(state="normal")
        self.widget.insert(tk.END, msg, tag)
        self.widget.see(tk.END)
        # Keep at most 500 lines to avoid unbounded memory growth
        lines = int(self.widget.index("end-1c").split(".")[0])
        if lines > 500:
            self.widget.delete("1.0", f"{lines - 500}.0")
        self.widget.configure(state="disabled")


def _setup_logging(text_widget: scrolledtext.ScrolledText):
    log_dir = os.path.join(APP_DIR, "logs")
    os.makedirs(log_dir, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Prevent duplicate handlers on repeated imports
    root_logger.handlers.clear()

    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(message)s", "%H:%M:%S")

    fh = logging.FileHandler(os.path.join(log_dir, "debug.log"), encoding="utf-8")
    fh.setFormatter(fmt)
    root_logger.addHandler(fh)

    th = _TextHandler(text_widget)
    th.setFormatter(fmt)
    root_logger.addHandler(th)


# ── Main application class ─────────────────────────────────────────────────────

class App:
    # Colours
    CLR_START  = "#2e7d32"
    CLR_STOP   = "#c62828"
    CLR_LOG_BG = "#1e1e1e"
    CLR_LOG_FG = "#d4d4d4"
    FONT_MONO  = ("Consolas", 8)
    FONT_UI    = ("Segoe UI", 9)
    FONT_BOLD  = ("Segoe UI", 9, "bold")

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("CHC Consultores — BLs BOT · asyncio y progreso persistente")
        self.root.resizable(True, True)
        self.root.minsize(620, 600)

        self.config = load_config()

        # Runtime state
        self.duals_df            = None
        self._loaded_file_path   = None   # path of the file currently open
        self.stop_event          = threading.Event()
        self._worker_thread  = None
        self._processing     = False
        self._loading_data = False
        self._loading_thread = None
        self._loading_mask = None
        self._loading_controls = []
        self.events = queue.Queue()
        self.last_summary = None
        self.last_output_folder = None
        self._network_waiting = False

        self._build_ui()
        _setup_logging(self.log_area)
        self._load_saved_data()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self.event_poll_id = self.root.after(100, self._poll_events)

    # ══════════════════════════════════════════════════════════════════════════
    # UI construction
    # ══════════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TNotebook.Tab", font=self.FONT_BOLD, padding=[12, 4])
        style.configure("Section.TLabel", font=self.FONT_BOLD, foreground="#333333")
        style.configure("Hint.TLabel",    font=("Segoe UI", 8), foreground="#777777")

        # Custom button colours via map (clam supports foreground map)
        style.configure("Start.TButton", font=self.FONT_BOLD,
                        foreground="white", background=self.CLR_START)
        style.map("Start.TButton",
                  background=[("active", "#1b5e20"), ("disabled", "#aaaaaa")])

        style.configure("Stop.TButton", font=self.FONT_BOLD,
                        foreground="white", background=self.CLR_STOP)
        style.map("Stop.TButton",
                  background=[("active", "#7f0000"), ("disabled", "#aaaaaa")])

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        tab_proc = ttk.Frame(self.notebook, padding=12)
        tab_cfg  = ttk.Frame(self.notebook, padding=12)
        self.notebook.add(tab_proc, text="  Procesamiento  ")
        self.notebook.add(tab_cfg,  text="  Configuración  ")

        self._build_processing_tab(tab_proc)
        self._build_settings_tab(tab_cfg)

    # ── Processing tab ─────────────────────────────────────────────────────────

    def _build_processing_tab(self, parent: ttk.Frame):
        # File section
        file_lf = ttk.LabelFrame(parent, text=" Base de BLs — Excel o SQLite ", padding=8)
        file_lf.pack(fill="x", pady=(0, 8))

        self.file_path_var = tk.StringVar(value="Ningún archivo seleccionado.")
        ttk.Label(file_lf, textvariable=self.file_path_var,
                  foreground="#555555", wraplength=560,
                  anchor="w").pack(fill="x", pady=(0, 6))
        btn_row = ttk.Frame(file_lf)
        btn_row.pack(fill="x")

        self.file_button = ttk.Button(btn_row, text="Seleccionar base…", command=self._select_file)
        self.file_button.pack(side="left")

        ttk.Label(btn_row, text="  Hoja:").pack(side="left")

        self.sheet_combo_var = tk.StringVar()
        self.sheet_combo = ttk.Combobox(
            btn_row, textvariable=self.sheet_combo_var,
            state="disabled", width=24,
        )
        self.sheet_combo.pack(side="left", padx=(4, 0))
        self.sheet_combo.bind("<<ComboboxSelected>>", self._on_sheet_selected)

        # Progress section
        prog_lf = ttk.LabelFrame(parent, text=" Progreso ", padding=8)
        prog_lf.pack(fill="x", pady=(0, 8))

        self.status_var = tk.StringVar(value="Esperando para iniciar…")
        ttk.Label(prog_lf, textvariable=self.status_var,
                  foreground="#333333").pack(anchor="w", pady=(0, 4))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            prog_lf, variable=self.progress_var,
            maximum=100, length=570
        )
        self.progress_bar.pack(fill="x", pady=(0, 4))

        self.rows_var = tk.StringVar(value="")
        ttk.Label(prog_lf, textvariable=self.rows_var,
                  foreground="#555555").pack(anchor="w")
        table_frame = ttk.Frame(prog_lf)
        table_frame.pack(fill='both', expand=True, pady=(5, 0))
        self.job_table = ttk.Treeview(table_frame, columns=('row', 'bl', 'state', 'attempts', 'rows', 'error'),
                                      show='headings', height=5)
        for name, title, width in zip(('row', 'bl', 'state', 'attempts', 'rows', 'error'),
            ('Fila', 'BL original', 'Estado', 'Intentos', 'Registros', 'Último error'), (55, 170, 100, 65, 75, 210)):
            self.job_table.heading(name, text=title)
            self.job_table.column(name, width=width, stretch=name == 'error')
        scrollbar = ttk.Scrollbar(table_frame, command=self.job_table.yview)
        scrollbar.pack(side='right', fill='y')
        self.job_table.configure(yscrollcommand=scrollbar.set)
        self.job_table.pack(fill='both', expand=True)

        # Action buttons
        btn_frame = ttk.Frame(parent)
        btn_frame.pack(fill="x", pady=(0, 8))

        self.start_btn = ttk.Button(
            btn_frame, text="▶  Iniciar",
            command=self._start, style="Start.TButton", width=14
        )
        self.start_btn.pack(side="left", padx=(0, 6))

        self.stop_btn = ttk.Button(
            btn_frame, text="■  Detener",
            command=self._stop, style="Stop.TButton",
            state="disabled", width=14
        )
        self.stop_btn.pack(side="left", padx=(0, 6))

        self.new_batch_button = ttk.Button(
            btn_frame, text="↺  Nueva descarga",
            command=self._reset_progress
        )
        self.new_batch_button.pack(side="left", padx=(0, 6))

        ttk.Button(
            btn_frame, text="📂  Abrir carpeta de resultados",
            command=self._open_output_folder
        ).pack(side="right")

        # Log area
        log_lf = ttk.LabelFrame(parent, text=" Registro de actividad ", padding=8)
        log_lf.pack(fill="both", expand=True)

        self.log_area = scrolledtext.ScrolledText(
            log_lf, height=12, state="disabled",
            font=self.FONT_MONO,
            background=self.CLR_LOG_BG, foreground=self.CLR_LOG_FG,
            wrap="word", relief="flat",
        )
        self.log_area.pack(fill="both", expand=True)

        ttk.Button(
            log_lf, text="Limpiar registro",
            command=self._clear_log
        ).pack(anchor="e", pady=(4, 0))

    # ── Settings tab ───────────────────────────────────────────────────────────

    def _build_settings_tab(self, parent: ttk.Frame):
        # Scrollable canvas wrapper
        canvas = tk.Canvas(parent, borderwidth=0, highlightthickness=0)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        inner = ttk.Frame(canvas)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_frame_configure(e):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(e):
            canvas.itemconfig(window_id, width=e.width)

        inner.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scroll
        def _on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        self._populate_settings(inner)

    def _populate_settings(self, sf: ttk.Frame):
        """Fill the scrollable settings inner frame."""
        # ── RUTAS ──────────────────────────────────────────────────────────────
        self._section(sf, "RUTAS")

        self.out_path_var = tk.StringVar(value=self.config.get("output_base_path", ""))
        self._path_row(
            sf, "Carpeta de resultados:",
            self.out_path_var, mode="dir",
            hint="Carpeta donde se guardarán los archivos CSV de salida.",
        )

        # ── RANGO DE FECHAS ────────────────────────────────────────────────────
        self._section(sf, "RANGO DE FECHAS PARA LA BÚSQUEDA")

        self.fecha_ini_var = tk.StringVar(value=self.config.get("fecha_inicio", "01/01/2025"))
        self._label_entry(
            sf, "Fecha de inicio (DD/MM/AAAA):", self.fecha_ini_var, width=14,
        )

        self.fecha_fin_var = tk.StringVar(value=self.config.get("fecha_fin", "31/12/2025"))
        self._label_entry(
            sf, "Fecha de fin     (DD/MM/AAAA):", self.fecha_fin_var, width=14,
        )
        self.dates_from_input_var = tk.BooleanVar(value=self.config.get('dates_from_input', True))
        ttk.Checkbutton(sf, text='Usar el mes de arribo de cada BL de la base',
                        variable=self.dates_from_input_var).pack(anchor='w', padx=10, pady=5)

        # ── PROCESAMIENTO ──────────────────────────────────────────────────────
        self._section(sf, "PROCESAMIENTO")

        self.hilos_var = tk.IntVar(value=self.config.get("cant_hilos", 2))
        self._label_spinbox(
            sf, "Contextos Playwright simultáneos:", self.hilos_var, from_=1, to=20,
            hint="Todos comparten un Chromium. Se recomienda iniciar con 2–4.",
        )

        self.retries_var = tk.IntVar(value=self.config.get("max_retries", 3))
        self._label_spinbox(
            sf, "Intentos ante errores de conexión:", self.retries_var, from_=1, to=10,
            hint="Incluye el primero. Siempre consulta exactamente el BL original.",
        )

        self.timeout_var = tk.IntVar(value=self.config.get("timeout", 30))
        self._label_spinbox(
            sf, "Tiempo de espera máximo (seg):", self.timeout_var, from_=5, to=120,
            hint="Segundos que espera por cada elemento en la página web.",
        )

        self.headless_var = tk.BooleanVar(value=self.config.get("headless", True))
        self.reuse_context_var = tk.BooleanVar(value=self.config.get('reuse_context', True))
        ttk.Checkbutton(sf, text='Reutilizar la sesión de cada trabajador',
                        variable=self.reuse_context_var).pack(anchor='w', padx=10, pady=5)
        cb_frame = ttk.Frame(sf)
        cb_frame.pack(anchor="w", padx=10, pady=(6, 2))
        ttk.Checkbutton(
            cb_frame,
            text="Modo silencioso — ejecutar sin mostrar el navegador",
            variable=self.headless_var,
        ).pack(anchor="w")
        ttk.Label(
            cb_frame,
            text="    Desmarcar solo para depuración; reduce el rendimiento.",
            style="Hint.TLabel",
        ).pack(anchor="w")

        # ── OPCIONES AVANZADAS ─────────────────────────────────────────────────
        self._section(sf, "OPCIONES AVANZADAS")

        ttk.Label(sf, text='Iniciar recupera por BL los pendientes de la base cargada.',
                  style='Hint.TLabel', wraplength=550).pack(anchor='w', padx=10, pady=6)

        ttk.Separator(sf, orient="horizontal").pack(fill="x", padx=10, pady=12)
        ttk.Button(
            sf, text="   Guardar configuración   ",
            command=self._save_settings,
        ).pack(pady=(0, 16))

    # ── Settings widget helpers ────────────────────────────────────────────────

    def _section(self, parent: ttk.Frame, text: str):
        ttk.Separator(parent, orient="horizontal").pack(fill="x", padx=10, pady=(10, 2))
        ttk.Label(parent, text=text, style="Section.TLabel").pack(
            anchor="w", padx=10, pady=(2, 4)
        )

    def _path_row(self, parent, label, var, mode="dir", filetypes=None, hint=""):
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=10, pady=(2, 0))
        ttk.Label(row, text=label, width=30, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=var, width=32).pack(side="left", padx=(0, 4))

        def browse():
            path = (
                filedialog.askdirectory(title=label)
                if mode == "dir"
                else filedialog.askopenfilename(
                    title=label, filetypes=filetypes or []
                )
            )
            if path:
                var.set(path)

        ttk.Button(row, text="Examinar…", command=browse).pack(side="left")
        if hint:
            ttk.Label(parent, text=f"    {hint}", style="Hint.TLabel").pack(
                anchor="w", padx=10, pady=(0, 4)
            )

    def _label_entry(self, parent, label, var, width=20, hint=""):
        row = ttk.Frame(parent)
        row.pack(anchor="w", padx=10, pady=(2, 0))
        ttk.Label(row, text=label, width=36, anchor="w").pack(side="left")
        ttk.Entry(row, textvariable=var, width=width).pack(side="left")
        if hint:
            ttk.Label(parent, text=f"    {hint}", style="Hint.TLabel").pack(
                anchor="w", padx=10, pady=(0, 4)
            )

    def _label_spinbox(self, parent, label, var, from_, to, hint=""):
        row = ttk.Frame(parent)
        row.pack(anchor="w", padx=10, pady=(2, 0))
        ttk.Label(row, text=label, width=36, anchor="w").pack(side="left")
        ttk.Spinbox(row, from_=from_, to=to, textvariable=var, width=8).pack(side="left")
        if hint:
            ttk.Label(parent, text=f"    {hint}", style="Hint.TLabel").pack(
                anchor="w", padx=10, pady=(0, 4)
            )

    def _load_saved_data(self):
        sheet = self.config.get("sheet_name", "")
        folder = os.path.join(APP_DIR, 'data', 'Datos_Cargados')
        cached = os.path.join(folder, f'{sheet}.sqlite3')
        excel = os.path.join(folder, f'{sheet}.xlsx')
        if not os.path.exists(cached) and not os.path.exists(excel):
            logging.info(
                "Primera ejecución o sin datos en caché. "
                "Seleccione un archivo en la pestaña Procesamiento."
            )
            return
        self._loading_data = True
        self._show_loading()
        self.start_btn.configure(state='disabled')
        self.file_button.configure(state='disabled')
        self.new_batch_button.configure(state='disabled')
        self.status_var.set('Restaurando la base local…')
        self.progress_bar.configure(mode='indeterminate', variable='')
        self.progress_bar.start(15)
        self._loading_thread = threading.Thread(
            target=self._restore_cached_data, args=(sheet, cached, excel), daemon=True)
        self._loading_thread.start()

    def _show_loading(self):
        def disable_controls(parent):
            for widget in parent.winfo_children():
                if isinstance(widget, (ttk.Button, ttk.Entry, ttk.Checkbutton,
                                       ttk.Radiobutton, ttk.Notebook, ttk.Treeview)):
                    self._loading_controls.append((widget, 'disabled' in widget.state()))
                    widget.state(['disabled'])
                disable_controls(widget)
        disable_controls(self.root)
        self._loading_mask = tk.Frame(self.root, background='#edf2f7', takefocus=True)
        self._loading_mask.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._loading_mask.lift()
        self._loading_mask.bind('<Key>', lambda event: 'break')
        self._loading_mask.after_idle(self._loading_mask.focus_set)
        card = tk.Frame(self._loading_mask, background='white', width=440, height=240,
                        highlightbackground='#dce4ed', highlightthickness=1)
        card.place(relx=.5, rely=.5, anchor='center')
        card.pack_propagate(False)
        tk.Label(card, text='BLs BOT', font=('Segoe UI', 9, 'bold'),
                 foreground='#52718f', background='white').pack(pady=(25, 8))
        tk.Label(card, text='Cargando tu base', font=('Segoe UI', 18, 'bold'),
                 foreground='#18334e', background='white').pack()
        self.loading_message_var = tk.StringVar(value='Restaurando los datos guardados…')
        tk.Label(card, textvariable=self.loading_message_var, font=('Segoe UI', 10),
                 wraplength=390, foreground='#526477', background='white').pack(pady=(10, 14))
        self._loading_spinner = ttk.Progressbar(card, mode='indeterminate', length=340)
        self._loading_spinner.pack()
        self._loading_spinner.start(12)
        tk.Label(card, text='Los controles se habilitarán al terminar.', font=('Segoe UI', 9),
                 foreground='#738397', background='white').pack(pady=(14, 0))

    def _hide_loading(self):
        if self._loading_mask is not None:
            self._loading_spinner.stop()
            self._loading_mask.destroy()
            self._loading_mask = None
        for widget, was_disabled in self._loading_controls:
            if widget.winfo_exists() and not was_disabled:
                widget.state(['!disabled'])
        self._loading_controls.clear()

    def _restore_cached_data(self, sheet, cached, excel):
        started = time.perf_counter()
        try:
            data = None
            if os.path.exists(cached):
                try:
                    data = load_input_cache(cached)
                except Exception as exc:
                    logging.warning('No se pudo leer la caché SQLite; se intentará el Excel: %s', exc)
            if data is None:
                self.events.put({'kind': 'input_loading',
                    'message': 'Preparando la base local para próximas aperturas más rápidas…'})
                data = leer_bls(excel, sheet)
                try:
                    save_input_cache(data, cached, excel, sheet_name=sheet)
                except Exception as exc:
                    logging.warning('Base cargada; no se pudo guardar la caché rápida: %s', exc)
                    cached = excel
            elapsed = time.perf_counter() - started
            logging.info('Datos restaurados desde caché: %s (%d filas, %.3f s)', cached, len(data), elapsed)
            self.events.put({'kind': 'input_loaded', 'data': data, 'sheet': sheet,
                             'cache_path': cached, 'load_seconds': elapsed})
        except Exception as exc:
            logging.warning('No se pudo restaurar la base local: %s', exc)
            self.events.put({'kind': 'input_error', 'error': str(exc)})

    def _finish_input_load(self, event):
        self._loading_data = False
        self._hide_loading()
        self._idle_buttons()
        if event['kind'] == 'input_error':
            if event.get('selection'):
                self.sheet_combo_var.set(self.config.get('sheet_name', ''))
                self.status_var.set('No se pudo abrir la base seleccionada; la base anterior se conserva.')
                messagebox.showerror('Error al abrir la base', event['error'])
                return
            self.duals_df = None
            self.status_var.set('No se pudo restaurar la base local. Seleccione el Excel o SQLite nuevamente.')
            self.sheet_combo.configure(state='disabled')
            return
        self.duals_df = event['data']
        sheet = event['sheet']
        self.sheet_combo.configure(values=event.get('sheets', [sheet]), state='readonly')
        self.sheet_combo_var.set(sheet)
        self.file_path_var.set(f"Base local: {event['cache_path']}")
        self.status_var.set(f'Listo — {len(self.duals_df):,} filas (el progreso se recuperará al iniciar)')
        if event.get('selection'):
            self._loaded_file_path = event['source_path']
            self.config['sheet_name'] = sheet
            try:
                save_config(self.config)
            except OSError as exc:
                logging.warning('Base cargada; no se pudo guardar la configuración: %s', exc)
            self.last_summary = None
            self.last_output_folder = None
            self.progress_var.set(0)
            self.rows_var.set('')
            self.job_table.delete(*self.job_table.get_children())

    # ══════════════════════════════════════════════════════════════════════════
    # File selection
    # ══════════════════════════════════════════════════════════════════════════

    def _select_file(self):
        if self._processing or self._loading_data:
            return
        path = filedialog.askopenfilename(
            title="Seleccionar base de BLs — Excel o SQLite",
            filetypes=[('Bases de BLs', '*.xlsx *.sqlite3 *.sqlite *.db'),
                       ('Excel', '*.xlsx'), ('SQLite', '*.sqlite3 *.sqlite *.db')],
        )
        if not path:
            return

        self._load_sheet(path)

    def _on_sheet_selected(self, _event=None):
        """Called when the user picks a different sheet from the combobox."""
        sheet = self.sheet_combo_var.get()
        if self._loaded_file_path and sheet:
            self._load_sheet(self._loaded_file_path, sheet)

    def _load_sheet(self, path: str, sheet=None):
        """Discover and load either input format away from the Tk thread."""
        if self._processing or self._loading_data:
            return
        preferred = self.config.get('sheet_name', '')
        self._loading_data = True
        self._show_loading()
        self.loading_message_var.set('Leyendo la base seleccionada…')
        self.status_var.set('Cargando la base seleccionada…')
        self._loading_thread = threading.Thread(
            target=self._read_selected_file, args=(path, sheet, preferred), daemon=True)
        self._loading_thread.start()

    def _read_selected_file(self, path, sheet, preferred):
        started = time.perf_counter()
        try:
            sheets = input_sheets(path)
            selected = sheet if sheet is not None else preferred if preferred in sheets else sheets[0]
            if selected not in sheets:
                raise ValueError(f'La base no contiene la hoja {selected!r}.')
            data = load_input_file(path, selected)
            cached = path
            try:
                cached = self._cache_sheet(path, selected, data)
            except Exception as exc:
                logging.warning('Base cargada; no se pudo guardar la caché rápida: %s', exc)
            elapsed = time.perf_counter() - started
            logging.info('Base cargada: %s · hoja %s (%d filas, %.3f s)', path, selected, len(data), elapsed)
            self.events.put({'kind': 'input_loaded', 'selection': True, 'data': data,
                             'sheet': selected, 'sheets': sheets, 'cache_path': cached,
                             'source_path': path, 'load_seconds': elapsed})
        except Exception as exc:
            logging.warning('No se pudo abrir la base seleccionada: %s', exc)
            self.events.put({'kind': 'input_error', 'selection': True, 'error': str(exc)})

    def _cache_sheet(self, source_path: str, sheet_name: str, df):
        """Save the loaded sheet to data/Datos_Cargados/ for resume support."""
        dest_dir = os.path.join(APP_DIR, "data", "Datos_Cargados")
        dest = os.path.join(dest_dir, f"{sheet_name}.sqlite3")
        if os.path.normcase(os.path.abspath(source_path)) != os.path.normcase(os.path.abspath(dest)):
            save_input_cache(df, dest, source_path, sheet_name=sheet_name)
        return dest

    # ══════════════════════════════════════════════════════════════════════════
    # Settings save
    # ══════════════════════════════════════════════════════════════════════════

    def _collect_settings(self):
        self.config["output_base_path"]      = self.out_path_var.get().strip()
        self.config["fecha_inicio"]          = self.fecha_ini_var.get().strip()
        self.config["fecha_fin"]             = self.fecha_fin_var.get().strip()
        self.config["cant_hilos"]            = self.hilos_var.get()
        self.config["max_retries"]           = self.retries_var.get()
        self.config["timeout"]              = self.timeout_var.get()
        self.config["headless"]              = self.headless_var.get()
        self.config['dates_from_input'] = self.dates_from_input_var.get()
        self.config['reuse_context'] = self.reuse_context_var.get()
        if not 1 <= self.config['cant_hilos'] <= 20:
            raise ValueError('Elija entre 1 y 20 consultas simultáneas.')
        if not 1 <= self.config['max_retries'] <= 10:
            raise ValueError('Elija entre 1 y 10 intentos de conexión.')
        if not 5 <= self.config['timeout'] <= 120:
            raise ValueError('El tiempo de espera debe estar entre 5 y 120 segundos.')
        if not self.config['dates_from_input']:
            first = datetime.strptime(self.config['fecha_inicio'], '%d/%m/%Y')
            last = datetime.strptime(self.config['fecha_fin'], '%d/%m/%Y')
            if first > last:
                raise ValueError('La fecha de inicio debe ser anterior o igual a la de fin.')

    def _save_settings(self):
        try:
            self._collect_settings()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror('Configuración inválida', str(exc))
            return
        save_config(self.config)
        messagebox.showinfo(
            "Configuración guardada",
            "La configuración se guardó correctamente.",
        )
        logging.info("Configuración guardada.")

    # ══════════════════════════════════════════════════════════════════════════
    # Processing
    # ══════════════════════════════════════════════════════════════════════════

    def _start(self):
        if self._processing or self._loading_data:
            return
        if self.duals_df is None or self.duals_df.empty:
            messagebox.showwarning(
                "Sin datos",
                "Primero seleccione una base Excel de BLs en la pestaña Procesamiento.",
            )
            return

        try:
            BLSProcessor.validate_runtime()
        except RuntimeError as exc:
            messagebox.showerror(
                "Playwright no disponible",
                str(exc),
            )
            return

        try:
            self._collect_settings()
        except (ValueError, tk.TclError) as exc:
            messagebox.showerror('Configuración inválida', str(exc))
            return
        save_config(self.config)

        self.job_table.delete(*self.job_table.get_children())
        self.last_summary = None
        self.file_button.configure(state='disabled')
        self.sheet_combo.configure(state='disabled')
        self.new_batch_button.configure(state='disabled')

        self.stop_event.clear()
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.status_var.set("Procesando…")
        logging.info(
            f"Iniciando procesamiento. Hoja='{self.config['sheet_name']}', "
            f"Trabajadores={self.config['cant_hilos']}. Recuperando pendientes desde SQLite."
        )
        self._processing = True
        self._worker_thread = threading.Thread(target=self._run, daemon=True)
        self._worker_thread.start()

    def _stop(self):
        self.stop_event.set()
        self.status_var.set("Deteniendo — esperando que los hilos terminen…")
        self.stop_btn.configure(state="disabled")
        logging.info("Detención solicitada por el usuario.")

    def _run(self):
        cfg = dict(self.config, event_callback=self.events.put)
        try:
            processor = BLSProcessor(cfg, self.stop_event)
            result = processor.run(self.duals_df)
            self.events.put({'kind': 'done', 'summary': result, 'stopped': self.stop_event.is_set()})
        except Exception as exc:
            logging.exception('Error general en el procesamiento')
            self.events.put({'kind': 'error', 'error': str(exc)})

    def _poll_events(self):
        for _ in range(200):
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            if event['kind'] in ('input_loaded', 'input_error'):
                self._finish_input_load(event)
            elif event['kind'] == 'input_loading':
                self.status_var.set(event['message'])
                self.loading_message_var.set(event['message'])
            elif event['kind'] == 'done':
                self.last_summary = event['summary']
                self._on_stopped() if event['stopped'] else self._on_complete()
            elif event['kind'] == 'error':
                self._on_error(event['error'])
            else:
                self._display_progress(event)
        self.event_poll_id = self.root.after(100, self._poll_events)

    def _display_progress(self, event):
        if event.get('phase') in ('browser_setup', 'network_wait'):
            if event['phase'] == 'network_wait':
                self._network_waiting = True
            self.status_var.set(event['message'])
            if str(self.progress_bar.cget('mode')) != 'indeterminate':
                self.progress_bar.configure(mode='indeterminate', variable='')
                self.progress_bar.start(15)
            return
        if event.get('phase') == 'network_resumed':
            self._network_waiting = False
            self.status_var.set(event['message'])
        if not self._network_waiting:
            self._end_browser_setup()
        if event.get('phase') == 'browser_ready':
            self.status_var.set(event['message'])
        elif event.get('phase') == 'download' and not self._network_waiting:
            self.status_var.set('Consultando BL pendientes…')
        if event.get('output_folder'):
            self.last_output_folder = event['output_folder']
        self.last_summary = event
        total = event.get('total', 0)
        saved, pending, invalid = event.get('saved', 0), event.get('pending', 0), event.get('invalid', 0)
        self.progress_var.set(saved / total * 100 if total else 0)
        self.rows_var.set(f'{saved:,}/{total:,} BL guardados · {pending:,} pendientes · '
                          f"{event.get('running', 0)} descargando · {invalid} inválidos")
        if event.get('phase') == 'prepare':
            self.status_var.set('Preparando la selección y recuperando el progreso…')
        for job in event.get('rows', []) + ([event['job']] if 'job' in event else []):
            key = str(job['ordinal'])
            values = (job['ordinal'], job['bl'], job['state'], job['attempts'], job['result_count'], job['error'])
            if self.job_table.exists(key):
                self.job_table.item(key, values=values)
            else:
                if len(self.job_table.get_children()) >= 1000:
                    self.job_table.delete(self.job_table.get_children()[0])
                self.job_table.insert('', 'end', iid=key, values=values)

    def _idle_buttons(self):
        self._network_waiting = False
        self._end_browser_setup()
        self._processing = False
        self.start_btn.configure(state='normal')
        self.stop_btn.configure(state='disabled')
        self.file_button.configure(state='normal')
        self.sheet_combo.configure(state='readonly')
        self.new_batch_button.configure(state='normal')

    def _end_browser_setup(self):
        if str(self.progress_bar.cget('mode')) == 'indeterminate':
            self.progress_bar.stop()
            self.progress_bar.configure(mode='determinate', variable=self.progress_var)

    def _on_stopped(self):
        self._idle_buttons()
        self.status_var.set('Detenido. Iniciar continúa los BL pendientes.')

    def _on_complete(self):
        self._idle_buttons()
        result = self.last_summary or {}
        pending, invalid = result.get('pending', 0), result.get('invalid', 0)
        message = (f"{result.get('saved', 0):,} BL guardados ({result.get('empty_saved', 0):,} sin líneas) · "
                   f"{pending:,} pendientes · {invalid} inválidos.")
        if result.get('export_error'):
            message += ' El CSV no pudo exportarse; los datos guardados se conservan.'
        self.status_var.set(message)
        logging.info(message)
        if pending or invalid or result.get('export_error'):
            messagebox.showwarning('Ejecución finalizada con pendientes', message)
        else:
            messagebox.showinfo('Proceso completado', message)

    def _on_error(self, error):
        self._idle_buttons()
        self.status_var.set('La ejecución terminó con un error; el progreso se conserva.')
        messagebox.showerror('Error de procesamiento', str(error))

    def _reset_progress(self):
        if self.duals_df is None or self._processing:
            return
        if not messagebox.askyesno('Nueva descarga',
                'Se creará otro lote para consultar nuevamente esta base. '
                'Los resultados y el progreso anteriores se conservan. ¿Continuar?'):
            return
        self.config['batch_revision'] = datetime.now().isoformat(timespec='microseconds')
        save_config(self.config)
        self.last_summary = None
        self.progress_var.set(0)
        self.job_table.delete(*self.job_table.get_children())
        self.status_var.set('Listo para iniciar una nueva descarga.')

    def _open_output_folder(self):
        base = self.config.get("output_base_path", "").strip()
        if not base:
            base = os.path.join(APP_DIR, "output")
        sheet = self.config.get("sheet_name", "")
        folder = self.last_output_folder or (os.path.join(base, sheet) if sheet else base)
        os.makedirs(folder, exist_ok=True)
        os.startfile(folder)

    def _clear_log(self):
        self.log_area.configure(state="normal")
        self.log_area.delete("1.0", tk.END)
        self.log_area.configure(state="disabled")

    def _on_close(self):
        if self._loading_data:
            self.status_var.set('Cerrando — esperando que termine la preparación de la base…')
            self.root.after(100, self._wait_for_input_and_close)
            return
        if self._processing:
            answer = messagebox.askyesno(
                "Proceso en curso",
                "Hay un proceso en ejecución.\n\n"
                "¿Desea detenerlo y cerrar la aplicación?",
            )
            if not answer:
                return
            self.stop_event.set()
            self.status_var.set("Cerrando — esperando que Chromium termine...")
            self.start_btn.configure(state="disabled")
            self.stop_btn.configure(state="disabled")
            self.root.after(100, self._wait_for_worker_and_close)
            return
        self._finalize_close()

    def _wait_for_input_and_close(self):
        if self._loading_thread is not None and self._loading_thread.is_alive():
            self.root.after(100, self._wait_for_input_and_close)
            return
        self._finalize_close()

    def _wait_for_worker_and_close(self):
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self.root.after(100, self._wait_for_worker_and_close)
            return
        self._finalize_close()

    def _finalize_close(self):
        self._hide_loading()
        self._end_browser_setup()
        self.root.after_cancel(self.event_poll_id)
        for handler in list(logging.getLogger().handlers):
            handler.close()
            logging.getLogger().removeHandler(handler)
        self.root.destroy()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    if '--verificar-instalacion' in sys.argv:
        from core.self_test import verify
        verify(sys.argv[sys.argv.index('--verificar-instalacion') + 1])
    else:
        main()

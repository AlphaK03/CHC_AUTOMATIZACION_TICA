import sys
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
from pathlib import Path
import threading
import queue
import json


from data_store import REGIMENES, REGIMENES_IMPORTACION, RangeStore, RunLock, period_for, ranges_for
from runner import run_downloads
from exports import publish, publish_originals, atomic_json
from output_paths import output_path
import driver_updater

# ── Directorio raíz de la app ─────────────────────────────────────────────────
# En exe congelado: carpeta del .exe. En desarrollo: raíz del proyecto.
if getattr(sys, 'frozen', False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent.parent

# ── Directorio para archivos de estado (selección, config) ───────────────────
# Frozen → junto al exe | Dev → src/ (donde ya viven esos archivos)
if getattr(sys, 'frozen', False):
    _STATE_DIR = _BASE_DIR
else:
    _STATE_DIR = Path(__file__).parent

_SELECCION_FILE  = _STATE_DIR / "ultima_seleccion.json"
_APP_CONFIG_FILE = _STATE_DIR / "config.json"

# ── Configuración de la app (rutas configurables por el usuario) ───────────────
_DEFAULT_APP_CFG = {
    "edge_driver_path": str(_BASE_DIR / 'drivers' / 'msedgedriver.exe'),
    "output_folder":    "",   # vacío = _BASE_DIR / "DUAs_2025"
}
_app_cfg: dict = {}


def cargar_app_config() -> dict:
    if _APP_CONFIG_FILE.exists():
        with open(_APP_CONFIG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {**_DEFAULT_APP_CFG, **data}
    return dict(_DEFAULT_APP_CFG)


def guardar_app_config(cfg: dict) -> None:
    atomic_json(_APP_CONFIG_FILE, cfg)


def get_carpeta_base() -> Path:
    return output_path(_app_cfg.get('output_folder', ''), _BASE_DIR)


def get_edge_driver() -> str:
    return _app_cfg.get("edge_driver_path", _DEFAULT_APP_CFG["edge_driver_path"])

# ── Régimenes conocidos (orden canónico) ──────────────────────────────────────
def get_database_path():
    return _BASE_DIR / 'data' / 'duas.sqlite3'


_cancel_event = threading.Event()
_log_queue    = queue.Queue()


# ── Persistencia de selección ─────────────────────────────────────────────────

def guardar_seleccion(regimen, mes, anio, rango, dia_ini=None, dia_fin=None):
    datos = {"regimen": regimen, "mes": mes, "anio": anio, "rango": rango,
             "dia_ini_custom": dia_ini, "dia_fin_custom": dia_fin}
    atomic_json(_SELECCION_FILE, datos)


def cargar_seleccion():
    if _SELECCION_FILE.exists():
        with open(_SELECCION_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


# ── Lógica de descarga ────────────────────────────────────────────────────────

def iniciar_bot_con_parametros(regimen, mes, anio, rango, log, mostrar_navegador=True,
                               dia_ini_custom=None, dia_fin_custom=None):
    config = {'edge_driver_path': get_edge_driver(), 'mostrar_navegador': mostrar_navegador}
    return run_downloads(get_database_path(), config, [regimen], mes, anio, rango,
                         log, _cancel_event, dia_ini_custom, dia_fin_custom)


def unir_archivos_finales(mes, anio, modo_union, log, base=None, database=None):
    period = period_for(mes, anio)
    ranges = ranges_for(period, modo_union)
    database = database or get_database_path()
    base = output_path(base if base is not None else _app_cfg.get('output_folder', ''), _BASE_DIR)
    with RunLock(database):
        store = RangeStore(database)
        try:
            lists, missing = store.collect(period, ranges)
            if missing:
                return [], missing
            paths = publish(base, period, ranges, lists, store=store)
            for path, rows in zip(paths, lists):
                log(f'{Path(path).name}: {len(rows):,} DUAs guardados.')
            log(f'Entrega completa de {period}. Carpeta: {base}')
            log('También se exportaron los originales en las carpetas de cada régimen y mes.')
            return paths, []
        finally:
            store.close()


def exportar_originales(mes, anio, mode, log, base=None, database=None):
    period = period_for(mes, anio)
    database = database or get_database_path()
    base = output_path(base if base is not None else _app_cfg.get('output_folder', ''), _BASE_DIR)
    with RunLock(database):
        store = RangeStore(database)
        try:
            paths, pending = publish_originals(base, period, store, mode)
            for path in paths:
                log(f'Original guardado: {Path(path).relative_to(Path(base).resolve())}')
            for regimen, days in pending.items():
                log(f'{regimen}: faltan descargas para exportar los días {", ".join(map(str, days))}.')
            log(f'Originales exportados: {len(paths)}. Carpeta: {base}')
            return paths, pending
        finally:
            store.close()


def mostrar_interfaz():
    # ── Paleta ───────────────────────────────────────────────────────────────
    BG_ROOT  = "#F1F5F9"
    BG_CARD  = "#FFFFFF"
    BG_LOG   = "#0F172A"
    ACCENT   = "#2563EB"
    ACCENT_H = "#1D4ED8"
    SUCCESS  = "#16A34A"
    SUCCESS_H= "#15803D"
    DANGER   = "#DC2626"
    DANGER_H = "#B91C1C"
    SLATE    = "#475569"
    SLATE_H  = "#334155"
    DISABLED = "#E2E8F0"
    DIS_FG   = "#94A3B8"
    TEXT     = "#1E293B"
    MUTED    = "#64748B"
    BORDER   = "#E2E8F0"
    LOG_FG   = "#CBD5E1"

    F_LABEL   = ("Segoe UI", 9)
    F_BOLD    = ("Segoe UI", 9, "bold")
    F_SECTION = ("Segoe UI", 8, "bold")
    F_MONO    = ("Consolas", 9)

    # ── Cargar config al iniciar ──────────────────────────────────────────────
    global _app_cfg
    _app_cfg = cargar_app_config()

    seleccion_previa = cargar_seleccion()

    root = tk.Tk()
    root.title("Consulta de DUAs — AstraCode")
    busy = False
    closing = False
    root.configure(bg=BG_ROOT)
    root.minsize(860, 600)
    root.resizable(True, True)
    root.columnconfigure(1, weight=1)
    root.rowconfigure(0, weight=1)

    # ── TTK theme ─────────────────────────────────────────────────────────────
    style = ttk.Style()
    style.theme_use("clam")

    style.configure("TCombobox",
        fieldbackground=BG_CARD, background=BG_CARD,
        foreground=TEXT, bordercolor=BORDER,
        arrowcolor=SLATE, selectbackground=ACCENT,
        selectforeground="#FFFFFF", padding=5,
    )
    style.map("TCombobox",
        fieldbackground=[("readonly", BG_CARD), ("disabled", DISABLED)],
        foreground=[("readonly", TEXT), ("disabled", DIS_FG)],
        bordercolor=[("focus", ACCENT)],
    )
    style.configure("Card.TCheckbutton",
        background=BG_CARD, foreground=TEXT, font=F_LABEL,
    )
    style.map("Card.TCheckbutton",
        background=[("active", BG_CARD)],
        foreground=[("disabled", DIS_FG)],
    )

    # ── Helpers ───────────────────────────────────────────────────────────────
    def make_card(parent, title):
        """Frame con borde sutil que simula una card."""
        outer = tk.Frame(parent, bg=BORDER)
        outer.pack(fill="x", pady=(0, 10))
        inner = tk.Frame(outer, bg=BG_CARD, padx=16, pady=10)
        inner.pack(fill="x", padx=1, pady=1)
        tk.Label(inner, text=title, bg=BG_CARD, fg=MUTED,
                 font=F_SECTION).pack(anchor="w", pady=(0, 8))
        return inner

    def add_field(parent, label, options, default):
        tk.Label(parent, text=label, bg=BG_CARD, fg=MUTED,
                 font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 2))
        cb = ttk.Combobox(parent, values=options, state="readonly", font=F_LABEL)
        cb.set(default)
        cb.pack(fill="x")
        return cb

    HOVER = {SUCCESS: SUCCESS_H, ACCENT: ACCENT_H, DANGER: DANGER_H, SLATE: SLATE_H}

    def styled_btn(parent, text, bg, fg="#FFFFFF"):
        btn = tk.Button(
            parent, text=text, bg=bg, fg=fg,
            activebackground=HOVER.get(bg, bg), activeforeground=fg,
            disabledforeground=DIS_FG,
            relief="flat", bd=0, pady=9,
            font=F_BOLD, cursor="hand2",
        )
        btn._bg = bg
        def on_enter(e):
            if str(btn["state"]) != "disabled":
                btn.config(bg=HOVER.get(bg, bg), activebackground=HOVER.get(bg, bg))
        def on_leave(e):
            if str(btn["state"]) != "disabled":
                btn.config(bg=btn._bg, activebackground=HOVER.get(btn._bg, btn._bg))
        btn.bind("<Enter>", on_enter)
        btn.bind("<Leave>", on_leave)
        return btn

    # ── Opciones ──────────────────────────────────────────────────────────────
    opciones_mes   = [
        "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
        "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
    ]
    opciones_rango = ["Ambos", "Primera parte (1-15)", "Segunda parte (16-fin)", "Rango personalizado"]
    opciones_union = ["Ambas partes", "Primera parte (1-15)", "Segunda parte (16-fin)"]

    modo_masivo       = tk.BooleanVar()
    mostrar_navegador = tk.BooleanVar(value=True)

    # ── Paneles principales ───────────────────────────────────────────────────
    frame_left = tk.Frame(root, bg=BG_ROOT, width=310)
    frame_left.grid(row=0, column=0, sticky="ns", padx=(16, 8), pady=16)
    frame_left.grid_propagate(False)

    frame_right = tk.Frame(root, bg=BG_ROOT)
    frame_right.grid(row=0, column=1, sticky="nsew", padx=(8, 16), pady=16)
    frame_right.columnconfigure(0, weight=1)
    frame_right.rowconfigure(1, weight=1)

    # ── Card: Descarga ────────────────────────────────────────────────────────
    card_desc = make_card(frame_left, "DESCARGA")

    combo_regimen = add_field(
        card_desc, "Régimen", REGIMENES,
        seleccion_previa["regimen"] if seleccion_previa else REGIMENES[0]
    )

    # Mes y Año en una misma fila
    row_mes_anio = tk.Frame(card_desc, bg=BG_CARD)
    row_mes_anio.pack(fill="x", pady=(8, 0))
    row_mes_anio.columnconfigure(0, weight=3)
    row_mes_anio.columnconfigure(1, weight=1)

    f_mes = tk.Frame(row_mes_anio, bg=BG_CARD)
    f_mes.grid(row=0, column=0, sticky="ew", padx=(0, 6))
    tk.Label(f_mes, text="Mes", bg=BG_CARD, fg=MUTED,
             font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 2))
    combo_mes = ttk.Combobox(f_mes, values=opciones_mes, state="readonly", font=F_LABEL)
    combo_mes.set(seleccion_previa["mes"] if seleccion_previa else "Junio")
    combo_mes.pack(fill="x")

    f_anio = tk.Frame(row_mes_anio, bg=BG_CARD)
    f_anio.grid(row=0, column=1, sticky="ew")
    tk.Label(f_anio, text="Año", bg=BG_CARD, fg=MUTED,
             font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 2))
    combo_anio = ttk.Combobox(f_anio, values=[str(y) for y in range(2020, 2031)],
                               state="readonly", font=F_LABEL, width=6)
    combo_anio.set(seleccion_previa["anio"] if seleccion_previa else "2025")
    combo_anio.pack(fill="x")

    combo_rango = add_field(
        card_desc, "Rango a descargar", opciones_rango,
        seleccion_previa.get("rango", "Ambos") if seleccion_previa else "Ambos"
    )

    # Frame de días personalizado (visible solo con "Rango personalizado")
    frame_custom_rango = tk.Frame(card_desc, bg=BG_CARD)
    row_dias = tk.Frame(frame_custom_rango, bg=BG_CARD)
    row_dias.pack(fill="x")
    row_dias.columnconfigure(0, weight=1)
    row_dias.columnconfigure(1, weight=1)

    f_dia_ini = tk.Frame(row_dias, bg=BG_CARD)
    f_dia_ini.grid(row=0, column=0, sticky="ew", padx=(0, 4))
    tk.Label(f_dia_ini, text="Día inicio", bg=BG_CARD, fg=MUTED,
             font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 2))
    _var_dia_ini = tk.StringVar(value=str(seleccion_previa.get("dia_ini_custom", 1) if seleccion_previa else 1))
    spin_dia_ini = ttk.Spinbox(f_dia_ini, from_=1, to=31, width=5, font=F_LABEL, textvariable=_var_dia_ini)
    spin_dia_ini.pack(fill="x")

    f_dia_fin = tk.Frame(row_dias, bg=BG_CARD)
    f_dia_fin.grid(row=0, column=1, sticky="ew", padx=(4, 0))
    tk.Label(f_dia_fin, text="Día fin", bg=BG_CARD, fg=MUTED,
             font=("Segoe UI", 8)).pack(anchor="w", pady=(0, 2))
    _var_dia_fin = tk.StringVar(value=str(seleccion_previa.get("dia_fin_custom", 31) if seleccion_previa else 31))
    spin_dia_fin = ttk.Spinbox(f_dia_fin, from_=1, to=31, width=5, font=F_LABEL, textvariable=_var_dia_fin)
    spin_dia_fin.pack(fill="x")

    def on_rango_change(event=None):
        if combo_rango.get() == "Rango personalizado":
            frame_custom_rango.pack(fill="x", pady=(6, 0))
        else:
            frame_custom_rango.pack_forget()

    combo_rango.bind("<<ComboboxSelected>>", on_rango_change)
    on_rango_change()  # estado inicial

    # Checkboxes
    frame_checks = tk.Frame(card_desc, bg=BG_CARD)
    frame_checks.pack(fill="x", pady=(12, 0))

    def on_toggle_masivo():
        if modo_masivo.get():
            combo_regimen.config(state=tk.DISABLED)
        else:
            combo_regimen.config(state="readonly")

    ttk.Checkbutton(frame_checks, text="Todos los regímenes",
                    variable=modo_masivo, command=on_toggle_masivo,
                    style="Card.TCheckbutton").pack(anchor="w")
    ttk.Checkbutton(frame_checks, text="Mostrar navegador",
                    variable=mostrar_navegador,
                    style="Card.TCheckbutton").pack(anchor="w", pady=(6, 0))

    refresh_saved = tk.BooleanVar(value=False)
    ttk.Checkbutton(frame_checks, text="Volver a descargar rangos guardados", variable=refresh_saved,
                    style="Card.TCheckbutton").pack(anchor="w", pady=(6, 0))

    # Botones Iniciar / Cancelar
    frame_btns = tk.Frame(card_desc, bg=BG_CARD)
    frame_btns.pack(fill="x", pady=(14, 2))
    frame_btns.columnconfigure(0, weight=1)
    frame_btns.columnconfigure(1, weight=1)

    btn_iniciar  = styled_btn(frame_btns, "▶  Iniciar",  SUCCESS)
    btn_cancelar = styled_btn(frame_btns, "✕  Cancelar", DISABLED, fg=DIS_FG)
    btn_iniciar.grid(row=0, column=0, sticky="ew", padx=(0, 4))
    btn_cancelar.grid(row=0, column=1, sticky="ew", padx=(4, 0))
    btn_cancelar.config(state=tk.DISABLED, cursor="arrow")

    # ── Card: Unificación ─────────────────────────────────────────────────────
    card_union = make_card(frame_left, "EXPORTAR A EXCEL")

    combo_modo_union = add_field(
        card_union, "Parte a unir", opciones_union, "Ambas partes"
    )

    btn_unir = styled_btn(card_union, "Unir archivos finales", ACCENT)
    btn_unir.pack(fill="x", pady=(12, 2))
    btn_originales = styled_btn(card_union, "Exportar originales…", SLATE)
    btn_originales.pack(fill="x", pady=(6, 2))

    # ── Card: Herramientas ────────────────────────────────────────────────────
    card_tools = make_card(frame_left, "HERRAMIENTAS")

    btn_driver = styled_btn(card_tools, "Actualizar WebDriver", SLATE)
    btn_driver.pack(fill="x", pady=(0, 6))

    btn_config = styled_btn(card_tools, "Configuración de rutas", SLATE)
    btn_config.pack(fill="x", pady=(0, 2))

    # ── Panel Log ─────────────────────────────────────────────────────────────
    tk.Label(frame_right, text="Log de actividad", bg=BG_ROOT, fg=MUTED,
             font=F_BOLD).grid(row=0, column=0, sticky="w", pady=(0, 6))

    txt_log = scrolledtext.ScrolledText(
        frame_right, bg=BG_LOG, fg=LOG_FG, font=F_MONO,
        relief="flat", bd=0, state=tk.DISABLED, wrap=tk.WORD,
        insertbackground=LOG_FG, selectbackground=ACCENT,
        padx=12, pady=10,
    )
    txt_log.grid(row=1, column=0, sticky="nsew")

    # ── Funciones internas ────────────────────────────────────────────────────
    def append_log(msg):
        txt_log.config(state=tk.NORMAL)
        txt_log.insert(tk.END, msg + "\n")
        txt_log.see(tk.END)
        txt_log.config(state=tk.DISABLED)

    def log(msg):
        _log_queue.put(("log", msg))

    def set_buttons_idle():
        nonlocal busy
        busy = False
        for widget in (combo_mes, combo_anio, combo_rango, combo_modo_union, spin_dia_ini, spin_dia_fin):
            widget.config(state='readonly')
        for widget in frame_checks.winfo_children():
            widget.config(state='normal')
        on_toggle_masivo()
        btn_iniciar.config(state=tk.NORMAL,    bg=SUCCESS,  fg="#FFFFFF",
                           activebackground=SUCCESS_H, cursor="hand2")
        btn_cancelar.config(state=tk.DISABLED, bg=DISABLED, fg=DIS_FG,
                            activebackground=DISABLED, cursor="arrow")
        btn_unir.config(state=tk.NORMAL,       bg=ACCENT,   fg="#FFFFFF",
                        activebackground=ACCENT_H, cursor="hand2")
        btn_originales.config(state=tk.NORMAL, bg=SLATE, fg='#FFFFFF', cursor='hand2')
        btn_driver.config(state=tk.NORMAL,     bg=SLATE,    fg="#FFFFFF",
                          activebackground=SLATE_H, cursor="hand2")
        btn_config.config(state=tk.NORMAL,     bg=SLATE,    fg="#FFFFFF",
                          activebackground=SLATE_H, cursor="hand2")

    def set_buttons_busy():
        nonlocal busy
        busy = True
        for widget in (combo_regimen, combo_mes, combo_anio, combo_rango, combo_modo_union, spin_dia_ini, spin_dia_fin):
            widget.config(state='disabled')
        for widget in frame_checks.winfo_children():
            widget.config(state='disabled')
        btn_iniciar.config(state=tk.DISABLED,  bg=DISABLED, fg=DIS_FG,
                           activebackground=DISABLED, cursor="arrow")
        btn_cancelar.config(state=tk.NORMAL,   bg=DANGER,   fg="#FFFFFF",
                            activebackground=DANGER_H, cursor="hand2")
        btn_unir.config(state=tk.DISABLED,     bg=DISABLED, fg=DIS_FG,
                        activebackground=DISABLED, cursor="arrow")
        btn_originales.config(state=tk.DISABLED, bg=DISABLED, fg=DIS_FG, cursor='arrow')
        btn_driver.config(state=tk.DISABLED,   bg=DISABLED, fg=DIS_FG,
                          activebackground=DISABLED, cursor="arrow")
        btn_config.config(state=tk.DISABLED,   bg=DISABLED, fg=DIS_FG,
                          activebackground=DISABLED, cursor="arrow")

    # ── Poll de la queue (hilo → GUI) ─────────────────────────────────────────
    def poll_queue():
        try:
            while True:
                kind, data = _log_queue.get_nowait()
                if kind == "log":
                    append_log(data)
                elif kind == "done":
                    set_buttons_idle()
                elif kind == "unir_done":
                    set_buttons_idle()
                    if closing:
                        continue
                    guardados, faltantes = data
                    if faltantes:
                        messagebox.showerror(
                            "Unificación pendiente",
                            "No se publicó una nueva entrega:\n\n"
                            + "\n".join(faltantes)
                            + "\n\nDescarga o retoma los rangos pendientes. Si un Excel está abierto, ciérralo e intenta unir de nuevo."
                        )
                    elif guardados:
                        messagebox.showinfo(
                            "Unificación completada",
                            "Se generaron los siguientes archivos:\n\n"
                            + "\n".join(Path(p).name for p in guardados)
                            + "\n\nLos originales también están en las carpetas de cada régimen y mes."
                        )
                    else:
                        messagebox.showwarning("Sin datos",
                                               "Los archivos no contienen registros válidos.")
                elif kind == "driver_done":
                    set_buttons_idle()
                    if not closing:
                        messagebox.showinfo("WebDriver", data)
                elif kind == 'originales_done':
                    set_buttons_idle()
                    if not closing:
                        paths, pending, base = data
                        message = f'Se exportaron {len(paths)} archivos originales.\n\nCarpeta: {base}'
                        if pending:
                            message += '\n\nQuedan rangos sin completar. Solo se exportaron las quincenas o meses completos disponibles.'
                        messagebox.showinfo('Exportación de originales', message)
                elif kind == 'originales_error':
                    set_buttons_idle()
                    if not closing:
                        messagebox.showerror('No se pudieron exportar los originales', data)
                elif kind == "driver_error":
                    set_buttons_idle()
                    if not closing:
                        messagebox.showerror("Error al actualizar WebDriver", data)
        except queue.Empty:
            pass
        if closing and not busy:
            root.destroy()
            return
        root.after(100, poll_queue)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def on_submit():
        regimen = combo_regimen.get()
        mes     = combo_mes.get()
        anio    = combo_anio.get()
        rango   = combo_rango.get()

        dia_ini = None
        dia_fin = None
        if rango == "Rango personalizado":
            try:
                dia_ini = int(spin_dia_ini.get())
                dia_fin = int(spin_dia_fin.get())
            except ValueError:
                messagebox.showerror("Error", "Los días deben ser números válidos.")
                return
            if dia_ini < 1 or dia_fin > 31 or dia_ini > dia_fin:
                messagebox.showerror("Error", "Rango de días inválido (inicio ≤ fin, entre 1 y 31).")
                return

        try:
            ranges_for(period_for(mes, anio), rango, dia_ini, dia_fin)
        except ValueError as exc:
            messagebox.showerror("Fechas inválidas", str(exc))
            return
        guardar_seleccion(regimen, mes, anio, rango, dia_ini, dia_fin)
        _cancel_event.clear()
        set_buttons_busy()

        regimens = list(REGIMENES) if modo_masivo.get() else [regimen]
        config = {'edge_driver_path': get_edge_driver(), 'mostrar_navegador': mostrar_navegador.get()}
        database = get_database_path()
        refresh = refresh_saved.get()

        def run():
            try:
                run_downloads(database, config, regimens, mes, anio, rango, log, _cancel_event,
                              dia_ini, dia_fin, refresh)
            except Exception as exc:
                log(f'No se pudo terminar: {exc}. Los rangos pendientes se conservan.')
            finally:
                _log_queue.put(("done", None))

        threading.Thread(target=run, daemon=True).start()

    def on_cancelar():
        _cancel_event.set()
        log("Deteniendo la consulta; se conservarán los rangos pendientes...")

    def on_unir():
        mes        = combo_mes.get()
        anio       = combo_anio.get()
        modo_union = combo_modo_union.get()

        set_buttons_busy()
        btn_cancelar.config(state=tk.DISABLED)
        base, database = get_carpeta_base(), get_database_path()
        log(f"\n▶ Uniendo {modo_union.lower()} — {mes} {anio}...")

        def run():
            try:
                guardados, faltantes = unir_archivos_finales(mes, anio, modo_union, log, base, database)
                _log_queue.put(("unir_done", (guardados, faltantes)))
            except Exception as e:
                log(f"❌ Error inesperado al unir: {e}")
                _log_queue.put(("unir_done", ([], [str(e)])))

        threading.Thread(target=run, daemon=True).start()

    def on_actualizar_driver():
        set_buttons_busy()
        btn_cancelar.config(state=tk.DISABLED)
        log("\n▶ Verificando versión de WebDriver...")
        driver_path = get_edge_driver()

        def run():
            try:
                edge_ver   = driver_updater.get_edge_version()
                driver_ver = driver_updater.get_current_driver_version(driver_path)
                latest_ver = driver_updater.get_latest_compatible_version(edge_ver)
                log(f"   Edge instalado : {edge_ver}")
                log(f"   Driver actual  : {driver_ver or 'no encontrado'}")
                log(f"   Driver disponible: {latest_ver}")

                if (driver_ver and driver_ver.split(".")[:3] == edge_ver.split(".")[:3]
                        and tuple(map(int, driver_ver.split("."))) >= tuple(map(int, latest_ver.split(".")))):
                    _log_queue.put(("driver_done", f"El driver ya está actualizado ({driver_ver})."))
                    return

                log(f"   Descargando driver {latest_ver}...")
                last_pct = [0]

                def progress(pct, kb):
                    if int(pct) >= last_pct[0] + 10:
                        last_pct[0] = int(pct) // 10 * 10
                        log(f"   {last_pct[0]}% ({kb} KB)")

                driver_updater.download_driver(latest_ver, driver_path,
                                               progress_callback=progress)
                _log_queue.put(("driver_done", f"Driver actualizado a {latest_ver} correctamente.\n{driver_path}"))
            except Exception as e:
                _log_queue.put(("driver_error", str(e)))

        threading.Thread(target=run, daemon=True).start()

    def on_originales():
        mes, anio = combo_mes.get(), combo_anio.get()
        try:
            period_for(mes, anio)
        except ValueError as exc:
            messagebox.showerror('Mes inválido', str(exc))
            return
        win = tk.Toplevel(root)
        win.title('Exportar originales')
        win.configure(bg=BG_CARD, padx=18, pady=16)
        win.resizable(False, False)
        win.transient(root)
        win.grab_set()
        mode = tk.StringVar(value='halves')
        tk.Label(win, text=f'{mes} {anio} · todos los regímenes guardados',
                 bg=BG_CARD, fg=TEXT, font=F_BOLD).pack(anchor='w', pady=(0, 10))
        for text, value in [('Dos partes: 1–15 y 16–fin de mes', 'halves'),
                            ('Mes entero: ambas partes fusionadas', 'month')]:
            tk.Radiobutton(win, text=text, value=value, variable=mode, bg=BG_CARD,
                           fg=TEXT, activebackground=BG_CARD, font=F_LABEL).pack(anchor='w', pady=4)
        tk.Label(win, text='Cada régimen tendrá su carpeta. Solo se exportan rangos completos.',
                 bg=BG_CARD, fg=MUTED, font=('Segoe UI', 9)).pack(anchor='w', pady=10)

        def export():
            selected = mode.get()
            base, database = get_carpeta_base(), get_database_path()
            win.destroy()
            set_buttons_busy()
            btn_cancelar.config(state=tk.DISABLED)
            log(f'Exportando originales de {mes} {anio}…')
            def run():
                try:
                    paths, pending = exportar_originales(mes, anio, selected, log, base, database)
                    _log_queue.put(('originales_done', (paths, pending, str(base))))
                except Exception as exc:
                    _log_queue.put(('originales_error', str(exc)))
            threading.Thread(target=run, daemon=True).start()
        button = styled_btn(win, 'Exportar a Excel', ACCENT)
        button.config(command=export)
        button.pack(fill='x', pady=(6, 0))

    def on_configuracion():
        win = tk.Toplevel(root)
        win.title("Configuración de rutas")
        win.configure(bg=BG_ROOT)
        win.resizable(False, False)
        win.grab_set()

        card = tk.Frame(win, bg=BORDER)
        card.pack(fill="x", padx=20, pady=20)
        inner = tk.Frame(card, bg=BG_CARD, padx=20, pady=16)
        inner.pack(fill="x", padx=1, pady=1)

        def add_path_row(parent, label, current_val, browse_fn):
            tk.Label(parent, text=label, bg=BG_CARD, fg=MUTED,
                     font=("Segoe UI", 8)).pack(anchor="w", pady=(8, 2))
            row = tk.Frame(parent, bg=BG_CARD)
            row.pack(fill="x")
            entry = tk.Entry(row, font=F_LABEL, bg="#F8FAFC", relief="flat",
                             highlightbackground=BORDER, highlightthickness=1)
            entry.insert(0, current_val)
            entry.pack(side="left", fill="x", expand=True, ipady=5)
            tk.Button(row, text="...", bg=SLATE, fg="#FFFFFF", relief="flat",
                      font=F_LABEL, cursor="hand2", padx=8,
                      command=lambda e=entry: browse_fn(e)).pack(side="left", padx=(4, 0))
            return entry

        def browse_exe(entry):
            path = filedialog.askopenfilename(
                parent=win, title="Seleccionar msedgedriver.exe",
                filetypes=[("Ejecutable", "*.exe"), ("Todos", "*.*")]
            )
            if path:
                entry.delete(0, tk.END)
                entry.insert(0, path)

        def browse_dir(entry):
            path = filedialog.askdirectory(parent=win, title="Seleccionar carpeta de salida", mustexist=False)
            if path:
                entry.delete(0, tk.END)
                entry.insert(0, path)

        entry_driver = add_path_row(
            inner, "Ruta de msedgedriver.exe",
            _app_cfg.get("edge_driver_path", ""), browse_exe
        )

        tk.Label(inner, text="Carpeta de salida (vacío = DUAs_2025 junto a la app)",
                 bg=BG_CARD, fg=MUTED, font=("Segoe UI", 8)).pack(anchor="w", pady=(12, 2))
        row_out = tk.Frame(inner, bg=BG_CARD)
        row_out.pack(fill="x")
        entry_output = tk.Entry(row_out, font=F_LABEL, bg="#F8FAFC", relief="flat",
                                highlightbackground=BORDER, highlightthickness=1)
        entry_output.insert(0, _app_cfg.get("output_folder", ""))
        entry_output.pack(side="left", fill="x", expand=True, ipady=5)
        tk.Button(row_out, text="...", bg=SLATE, fg="#FFFFFF", relief="flat",
                  font=F_LABEL, cursor="hand2", padx=8,
                  command=lambda: browse_dir(entry_output)).pack(side="left", padx=(4, 0))
        tk.Label(inner, text='Si no existe, se creará al exportar. Las rutas relativas parten de la carpeta de la app.',
                 bg=BG_CARD, fg=MUTED, font=('Segoe UI', 8), wraplength=440,
                 justify='left').pack(anchor='w', pady=(6, 0))

        def on_save():
            global _app_cfg
            candidate = {**_app_cfg, 'edge_driver_path': entry_driver.get().strip(),
                         'output_folder': entry_output.get().strip()}
            try:
                destination = output_path(candidate['output_folder'], _BASE_DIR)
                guardar_app_config(candidate)
            except (OSError, ValueError) as exc:
                messagebox.showerror('No se pudo guardar la configuración', str(exc), parent=win)
                return
            _app_cfg = candidate
            log(f"✅ Configuración guardada.")
            log(f"   Driver  : {_app_cfg['edge_driver_path'] or '(por defecto)'}")
            log(f"   Salida  : {destination}")
            win.destroy()

        def on_reset():
            entry_driver.delete(0, tk.END)
            entry_driver.insert(0, _DEFAULT_APP_CFG["edge_driver_path"])
            entry_output.delete(0, tk.END)

        frame_btns_cfg = tk.Frame(inner, bg=BG_CARD)
        frame_btns_cfg.pack(fill="x", pady=(16, 0))
        tk.Button(frame_btns_cfg, text="Restaurar por defecto", bg=DISABLED, fg=TEXT,
                  relief="flat", font=F_LABEL, cursor="hand2", padx=10, pady=6,
                  command=on_reset).pack(side="left")
        tk.Button(frame_btns_cfg, text="Guardar", bg=SUCCESS, fg="#FFFFFF",
                  relief="flat", font=F_BOLD, cursor="hand2", padx=20, pady=6,
                  command=on_save).pack(side="right")

    btn_iniciar.config(command=on_submit)
    btn_cancelar.config(command=on_cancelar)
    btn_unir.config(command=on_unir)
    btn_originales.config(command=on_originales)
    btn_driver.config(command=on_actualizar_driver)
    btn_config.config(command=on_configuracion)

    def on_close():
        nonlocal closing
        closing = True
        if busy:
            _cancel_event.set()
            log('Cerrando cuando termine la operación actual...')
    root.protocol('WM_DELETE_WINDOW', on_close)
    poll_queue()
    root.mainloop()


if __name__ == "__main__":
    mostrar_interfaz()

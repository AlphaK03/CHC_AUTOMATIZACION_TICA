import os
import json
import asyncio
from datetime import datetime
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
from conocimientos_panel import KnowledgeProgressWindow
from bls_base_panel import BLSBaseWindow
from organizar_resultados import organize_results
from utils import load_config

from manifest_scraper import (
    run_manifest_bot,
    run_manifest_duas_bot,
    run_manifest_movimientos_bot,
    run_manifest_conocimientos_bot,
    run_manifest_contenedores_bot,
)

PREFS_FILE = os.path.join(os.path.dirname(__file__), "manifest_prefs.json")

MONTHS = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"
]


def load_prefs():
    now = datetime.now()
    default = {
        "modes": {"maritimo": True, "aereo": False, "terrestre": False},
        "month": now.month,
        "year": now.year,
        "flow": "tabla",
    }
    if not os.path.exists(PREFS_FILE):
        return default
    try:
        with open(PREFS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        default.update(data)
        if "modes" in data:
            default["modes"].update(data["modes"])
        return default
    except Exception:
        return default


def save_prefs(prefs):
    try:
        with open(PREFS_FILE, "w", encoding="utf-8") as f:
            json.dump(prefs, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error guardando preferencias: {e}")


def main():
    organize_results(load_config())
    prefs = load_prefs()

    root = ttk.Window(title="TICA Manifiestos - Bot", themename="darkly", resizable=(False, False))

    var_maritimo  = ttk.BooleanVar(value=prefs["modes"].get("maritimo", True))
    var_aereo     = ttk.BooleanVar(value=prefs["modes"].get("aereo", False))
    var_terrestre = ttk.BooleanVar(value=prefs["modes"].get("terrestre", False))
    var_month     = ttk.StringVar(value=MONTHS[prefs.get("month", datetime.now().month) - 1])
    var_year      = ttk.IntVar(value=prefs.get("year", datetime.now().year))
    var_flow      = ttk.StringVar(value=prefs.get("flow", "tabla"))
    var_status    = ttk.StringVar(value="Listo.")
    knowledge_window = None
    bls_window = None

    pad = {"padx": 12, "pady": 6}

    # ── Modalidades ──────────────────────────────────────────────────────────
    frm_modes = ttk.LabelFrame(root, text="Modalidades", )
    frm_modes.pack(fill=X, padx=16, pady=(14, 6))

    ttk.Checkbutton(frm_modes, text="Maritimo",  variable=var_maritimo,
                    bootstyle="success-round-toggle").pack(side=LEFT, padx=10)
    ttk.Checkbutton(frm_modes, text="Aereo",     variable=var_aereo,
                    bootstyle="success-round-toggle").pack(side=LEFT, padx=10)
    ttk.Checkbutton(frm_modes, text="Terrestre", variable=var_terrestre,
                    bootstyle="success-round-toggle").pack(side=LEFT, padx=10)

    # ── Periodo ───────────────────────────────────────────────────────────────
    frm_period = ttk.LabelFrame(root, text="Periodo", )
    frm_period.pack(fill=X, padx=16, pady=6)

    ttk.Label(frm_period, text="Mes:").grid(row=0, column=0, sticky=E, **pad)
    ttk.Combobox(frm_period, textvariable=var_month, values=MONTHS,
                 state="readonly", width=16).grid(row=0, column=1, sticky=W, **pad)

    ttk.Label(frm_period, text="Ano:").grid(row=1, column=0, sticky=E, **pad)
    ttk.Spinbox(frm_period, from_=2000, to=2100, textvariable=var_year,
                width=10).grid(row=1, column=1, sticky=W, **pad)

    # ── Flujo ────────────────────────────────────────────────────────────────
    frm_flow = ttk.LabelFrame(root, text="Flujo a ejecutar", )
    frm_flow.pack(fill=X, padx=16, pady=6)

    flows = [
        ("Tabla de manifiestos (CSV)",  "tabla"),
        ("Recorrer DUAs por manifiesto", "duas"),
        ("Movimientos de manifiesto",    "movimientos"),
        ("Conocimientos asociados",      "conocimientos"),
        ("Contenedores asociados",       "contenedores"),
    ]
    for label, value in flows:
        ttk.Radiobutton(frm_flow, text=label, variable=var_flow,
                        value=value, bootstyle=INFO).pack(anchor=W, pady=2)

    def open_bls_base():
        nonlocal bls_window
        if bls_window and bls_window.window.winfo_exists():
            bls_window.window.lift()
        else:
            bls_window = BLSBaseWindow(root)

    tools_frame = ttk.LabelFrame(root, text='Bases para otros bots')
    tools_frame.pack(fill=X, padx=16, pady=6)
    ttk.Button(tools_frame, text='Crear base para BLs_BOT', command=open_bls_base,
               bootstyle=INFO).pack(padx=12, pady=8, fill=X)

    # ── Status ────────────────────────────────────────────────────────────────
    lbl_status = ttk.Label(root, textvariable=var_status, bootstyle=WARNING,
                           font=("", 9, "italic"))
    lbl_status.pack(padx=16, pady=(8, 4), anchor=W)

    # ── Boton ─────────────────────────────────────────────────────────────────
    def set_status(msg, style=WARNING):
        var_status.set(msg)
        lbl_status.configure(bootstyle=style)
        root.update_idletasks()

    def on_run():
        nonlocal knowledge_window
        if knowledge_window and knowledge_window.window.winfo_exists() and knowledge_window.active:
            knowledge_window.window.lift()
            return
        modes = []
        if var_maritimo.get():  modes.append("maritimo")
        if var_aereo.get():     modes.append("aereo")
        if var_terrestre.get(): modes.append("terrestre")

        if not modes:
            messagebox.showwarning("Sin modos", "Selecciona al menos una modalidad.")
            return

        try:
            month = MONTHS.index(var_month.get()) + 1
        except ValueError:
            messagebox.showerror("Error", "Mes invalido seleccionado.")
            return

        year = var_year.get()
        if year < 2000 or year > 2100:
            messagebox.showerror("Error", "Ano fuera de rango (2000-2100).")
            return

        save_prefs({
            "modes": {
                "maritimo":  var_maritimo.get(),
                "aereo":     var_aereo.get(),
                "terrestre": var_terrestre.get(),
            },
            "month": month,
            "year":  year,
            "flow":  var_flow.get(),
        })

        flow = var_flow.get()
        if flow in ("conocimientos", "duas", "movimientos"):
            if knowledge_window and knowledge_window.window.winfo_exists():
                knowledge_window.close()
            runners = {'conocimientos': run_manifest_conocimientos_bot,
                       'duas': run_manifest_duas_bot, 'movimientos': run_manifest_movimientos_bot}
            knowledge_window = KnowledgeProgressWindow(
                root, runners[flow], modes, month, year,
                on_finished=lambda message: set_status(message), flow=flow)
            set_status("Progreso disponible en la ventana de descarga.")
            return
        flow_labels = {
            "tabla":        "Tabla de manifiestos (CSV)",
            "duas":         "Recorrer DUAs por manifiesto",
            "movimientos":  "Movimientos de manifiesto",
            "conocimientos":"Conocimientos asociados",
            "contenedores": "Contenedores asociados",
        }
        set_status(
            f"Ejecutando '{flow_labels.get(flow, flow)}': "
            f"{', '.join(modes)} — {MONTHS[month-1]} {year}...",
            WARNING,
        )

        try:
            if flow == "tabla":
                asyncio.run(run_manifest_bot(modes, month, year))
            elif flow == "duas":
                asyncio.run(run_manifest_duas_bot(modes, month, year))
            elif flow == "movimientos":
                asyncio.run(run_manifest_movimientos_bot(modes, month, year))
            elif flow == "conocimientos":
                asyncio.run(run_manifest_conocimientos_bot(modes, month, year))
            elif flow == "contenedores":
                asyncio.run(run_manifest_contenedores_bot(modes, month, year))
            else:
                raise ValueError(f"Flujo desconocido: {flow}")

            set_status("Proceso finalizado.", SUCCESS)
            if flow in ("tabla", "duas", "movimientos", "conocimientos", "contenedores"):
                messagebox.showinfo("Listo", "Proceso completado.")

        except Exception as e:
            set_status("Error durante la ejecucion.", DANGER)
            messagebox.showerror("Error", f"Ocurrio un error:\n{e}")

    ttk.Button(root, text="Ejecutar consulta", command=on_run,
               bootstyle=SUCCESS, width=26).pack(pady=(6, 16))

    def close_app():
        def close_bls():
            if bls_window and bls_window.window.winfo_exists():
                bls_window.close(after_close=root.destroy)
            else:
                root.destroy()
        if knowledge_window and knowledge_window.window.winfo_exists() and knowledge_window.active:
            knowledge_window.close(after_close=close_bls)
        else:
            close_bls()

    root.protocol('WM_DELETE_WINDOW', close_app)
    root.mainloop()


if __name__ == "__main__":
    main()

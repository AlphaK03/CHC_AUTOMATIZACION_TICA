"""Sección independiente de la app para generar bases BL sin navegar TICA."""
import os
import queue
import threading
from pathlib import Path
from tkinter import filedialog, messagebox

import ttkbootstrap as ttk

from bls_base import (BuildCancelled, available_periods, build_base, default_roots, OUTPUT_FORMATS,
                      default_selection, discover_sources, catalog_sources, choose_candidates)
from resultados import resolve_path, MONTHS
from utils import load_config

MODES = {'Todas': None, 'Marítimo': 'maritimo', 'Aéreo': 'aereo', 'Terrestre': 'terrestre'}
MODE_LABELS = {value: key for key, value in MODES.items() if value}
INPUT_KINDS = {'Preferir SQLite': 'preferred', 'Solo SQLite': 'SQLite',
               'Solo CSV': 'CSV', 'Solo Excel': 'XLSX', 'Todos los archivos': 'all'}
MONTH_LABELS = [name.capitalize() for name in MONTHS]
OUTPUT_CHOICES = {'Excel (.xlsx)': '.xlsx', 'SQLite (.sqlite3)': '.sqlite3'}
APP_INPUT, EXTERNAL_INPUT = 'Datos de esta app', 'Carpetas externas'


class BLSBaseWindow:
    def __init__(self, parent):
        self.window = ttk.Toplevel(parent)
        self.window.title('Crear base para BLs_BOT')
        width = min(860, self.window.winfo_screenwidth() - 60)
        height = min(650, self.window.winfo_screenheight() - 100)
        self.window.geometry(f'{width}x{height}')
        self.window.minsize(min(680, width), min(500, height))
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(2, weight=1)
        self.events = queue.Queue()
        self.stop = threading.Event()
        self.active = False
        self.after_close = None
        config = load_config()
        self.roots = default_roots(config)
        self.app_roots = list(self.roots)
        self.external_roots = []
        self.input_source = ttk.StringVar(value=APP_INPUT)
        self.sources, self.selected = {}, {}
        self.catalog, self.catalog_errors, self.loaded_paths = [], [], set()
        self.period_choices, self.period_keys = {}, {}
        self.scan_errors = []
        self.last_audit = None
        self.year = ttk.StringVar(value='Todos')
        self.month = ttk.StringVar(value='Todos')
        self.mode = ttk.StringVar(value='Todas')
        self.include_history = ttk.BooleanVar(value=False)
        self.input_kind = ttk.StringVar(value='Preferir SQLite')
        self.status = ttk.StringVar(value='Preparando opciones de entrada…')
        self.default_output = resolve_path(config.get('bases_bls_folder', 'bases_bls'))
        self.output_format = ttk.StringVar(value='Excel (.xlsx)')
        self.output = ttk.StringVar(value=str(self.default_output / 'Bls_sin_courier.xlsx'))
        self.output_trace_id = self.output.trace_add('write', self._output_path_changed)

        ttk.Label(self.window, text='Base BLS · Conocimientos sin courier',
                  padding=(12, 8)).grid(row=0, column=0, sticky='ew')
        inputs = ttk.Labelframe(self.window, text='1. Elegir datos', padding=8)
        inputs.grid(row=1, column=0, sticky='ew', padx=12, pady=(0, 8))
        roots_frame = ttk.Frame(inputs)
        roots_frame.pack(fill='x', pady=(0, 6))
        self.source_combo = ttk.Combobox(roots_frame, textvariable=self.input_source,
                                       values=(APP_INPUT,EXTERNAL_INPUT), state='readonly', width=21)
        self.source_combo.pack(side='left', padx=(0,8))
        self.source_combo.bind('<<ComboboxSelected>>', self.source_changed)
        self.roots_text = ttk.StringVar()
        ttk.Label(roots_frame, textvariable=self.roots_text, width=1).pack(side='left', fill='x', expand=True)
        self.add_button = ttk.Button(roots_frame, text='Agregar…', command=self.add_folder)
        self.add_button.pack(side='right', padx=3)
        self.clear_button = ttk.Button(roots_frame, text='Vaciar', command=self.clear_folders)
        self.clear_button.pack(side='right', padx=3)
        self._roots_label()

        filters = ttk.Frame(inputs)
        filters.pack(fill='x')
        self.filters = []
        for column, (title, var, values, width) in enumerate((
            ('Año', self.year, ['Todos'], 8),
            ('Mes', self.month, ['Todos'], 13),
            ('Modalidad', self.mode, ['Todas'], 12))):
            filters.columnconfigure(column, weight=1)
            ttk.Label(filters, text=title).grid(row=0, column=column, sticky='w', padx=(0, 8))
            combo = ttk.Combobox(filters, textvariable=var, values=values, state='readonly', width=width)
            combo.grid(row=1, column=column, sticky='ew', padx=(0, 8))
            combo.bind('<<ComboboxSelected>>', self.filter_changed)
            self.filters.append(combo)
        self.scan_button = ttk.Button(filters, text='Cargar datos', command=self.scan, bootstyle='primary')
        self.scan_button.grid(row=1, column=3, sticky='e')

        self.tabs = ttk.Notebook(self.window)
        self.tabs.grid(row=2, column=0, sticky='nsew', padx=12, pady=(0, 8))
        self.months_tab = ttk.Frame(self.tabs, padding=8)
        self.files_tab = ttk.Frame(self.tabs, padding=8)
        self.tabs.add(self.months_tab, text='2. Meses')
        self.tabs.add(self.files_tab, text='Archivos y opciones')
        options = ttk.Frame(self.files_tab)
        options.pack(fill='x', pady=(0, 8))
        ttk.Label(options, text='Leer:').pack(side='left')
        self.kind_combo = ttk.Combobox(options, textvariable=self.input_kind,
                                      values=list(INPUT_KINDS), state='readonly', width=21)
        self.kind_combo.pack(side='left', padx=8)
        self.kind_combo.bind('<<ComboboxSelected>>', self.filter_changed)
        self.history_check = ttk.Checkbutton(options, text='Incluir históricos',
                                            variable=self.include_history, command=self.refresh_catalog)
        self.history_check.pack(side='left', padx=8)

        periods_frame = self.months_tab
        period_actions = ttk.Frame(periods_frame)
        period_actions.pack(fill='x')
        self.period_summary = ttk.StringVar(value='Sin datos cargados')
        ttk.Label(period_actions, textvariable=self.period_summary, width=1).pack(side='left', fill='x', expand=True)
        self.period_all_button = ttk.Button(period_actions, text='Todos', command=lambda: self.select_periods(True))
        self.period_all_button.pack(side='right', padx=2)
        self.period_none_button = ttk.Button(period_actions, text='Ninguno', command=lambda: self.select_periods(False))
        self.period_none_button.pack(side='right', padx=2)
        period_table_frame = ttk.Frame(periods_frame)
        period_table_frame.pack(fill='both', expand=True, pady=(6, 0))
        self.period_table = ttk.Treeview(period_table_frame, columns=('use', 'period', 'mode', 'sources', 'state'),
                                        show='headings', selectmode='extended', height=7)
        for column, title, width in zip(('use', 'period', 'mode', 'sources', 'state'),
                ('Incluir', 'Mes', 'Modalidad', 'Fuentes', 'Descarga'),
                (55, 145, 95, 65, 270)):
            self.period_table.heading(column, text=title)
            self.period_table.column(column, width=width, stretch=column == 'state')
        period_scroll = ttk.Scrollbar(period_table_frame, command=self.period_table.yview)
        period_scroll.pack(side='right', fill='y')
        self.period_table.configure(yscrollcommand=period_scroll.set)
        period_horizontal = ttk.Scrollbar(period_table_frame, orient='horizontal', command=self.period_table.xview)
        period_horizontal.pack(side='bottom', fill='x')
        self.period_table.configure(xscrollcommand=period_horizontal.set)
        self.period_table.pack(side='left', fill='both', expand=True)
        self.period_table.bind('<Button-1>', self.toggle_period)
        self.period_table.bind('<space>', self.toggle_selected_periods)
        self.period_table.tag_configure('unavailable', foreground='#888888')
        self.empty_hint = ttk.Label(period_table_frame,
            text='Elige los filtros y pulsa Cargar datos.', wraplength=320, anchor='center', justify='center')
        self.empty_hint.place(relx=.5, rely=.5, anchor='center')

        pick = ttk.Frame(self.files_tab)
        pick.pack(fill='x')
        ttk.Label(pick, text='Archivos incluidos').pack(side='left')
        self.all_button = ttk.Button(pick, text='Todas', command=lambda: self.select_all(True))
        self.all_button.pack(side='right', padx=2)
        self.none_button = ttk.Button(pick, text='Ninguna', command=lambda: self.select_all(False))
        self.none_button.pack(side='right', padx=2)
        frame = ttk.Frame(self.files_tab)
        frame.pack(fill='both', expand=True)
        cols = ('use', 'period', 'mode', 'kind', 'rows', 'file')
        self.table = ttk.Treeview(frame, columns=cols, show='headings', selectmode='extended', height=5)
        for column, title, width in zip(cols, ('Usar', 'Mes', 'Modalidad', 'Formato', 'Filas', 'Archivo / hoja'),
                                        (50, 90, 90, 70, 75, 330)):
            self.table.heading(column, text=title)
            self.table.column(column, width=width, stretch=column == 'file')
        scrollbar = ttk.Scrollbar(frame, command=self.table.yview)
        scrollbar.pack(side='right', fill='y')
        self.table.configure(yscrollcommand=scrollbar.set)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=self.table.xview)
        horizontal.pack(side='bottom', fill='x')
        self.table.configure(xscrollcommand=horizontal.set)
        self.table.pack(side='left', fill='both', expand=True)
        self.table.bind('<Button-1>', self.toggle)
        self.table.bind('<space>', self.toggle_selected)

        self.footer = ttk.Frame(self.window, padding=(12, 0, 12, 10))
        self.footer.grid(row=3, column=0, sticky='ew')
        output_frame = ttk.Labelframe(self.footer, text='3. Guardar base', padding=8)
        output_frame.pack(fill='x')
        self.output_combo = ttk.Combobox(output_frame,textvariable=self.output_format,
                                       values=list(OUTPUT_CHOICES),state='readonly',width=19)
        self.output_combo.pack(side='left',padx=(0,8))
        self.output_combo.bind('<<ComboboxSelected>>', self.output_format_changed)
        self.output_entry = ttk.Entry(output_frame, textvariable=self.output)
        self.output_entry.pack(side='left', fill='x', expand=True)
        self.output_button = ttk.Button(output_frame, text='Guardar en…', command=self.choose_output)
        self.output_button.pack(side='left', padx=6)
        self.bar = ttk.Progressbar(self.footer, maximum=1)
        self.bar.pack(fill='x', pady=(8, 0))
        ttk.Label(self.footer, textvariable=self.status, width=1, padding=(0, 5)).pack(fill='x')
        actions = ttk.Frame(self.footer)
        actions.pack(fill='x')
        self.build_button = ttk.Button(actions, text='Generar base', bootstyle='success', command=self.generate)
        self.build_button.pack(side='right')
        self.stop_button = ttk.Button(actions, text='Detener', command=self.stop.set)
        self.stop_button.pack(side='right', padx=6)
        self.folder_button = ttk.Button(actions, text='Abrir carpeta', command=self.open_output)
        self.folder_button.pack(side='left')
        self.diagnostic_button = ttk.Button(actions, text='Diagnóstico', command=self.diagnostics)
        self.diagnostic_button.pack(side='left', padx=6)
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.poll_id = self.window.after(100, self.poll)
        self.refresh_catalog()

    def _roots_label(self):
        self.roots_text.set('Descargas actuales' if self.input_source.get()==APP_INPUT else
            f'{len(self.roots)} carpeta(s)' if self.roots else 'Agrega una carpeta')

    def source_changed(self, event=None):
        if self.active:
            return
        self.roots = list(self.app_roots if self.input_source.get()==APP_INPUT else self.external_roots)
        self._roots_label()
        self.refresh_catalog()

    def _buttons(self):
        for widget in (self.add_button, self.clear_button, self.scan_button, self.all_button,
                       self.period_all_button, self.period_none_button,
                       self.none_button, self.output_button, self.output_entry, self.history_check):
            widget.configure(state='disabled' if self.active else 'normal')
        for widget in self.filters:
            widget.configure(state='disabled' if self.active else 'readonly')
        self.kind_combo.configure(state='disabled' if self.active else 'readonly')
        self.source_combo.configure(state='disabled' if self.active else 'readonly')
        self.output_combo.configure(state='disabled' if self.active else 'readonly')
        external = self.input_source.get()==EXTERNAL_INPUT
        for widget in (self.add_button,self.clear_button):
            widget.configure(state='normal' if external and not self.active else 'disabled')
            if external:
                widget.pack(side='right',padx=3)
            else:
                widget.pack_forget()
        self.build_button.configure(state='normal' if not self.active and self.ready_to_build() else 'disabled')
        self.stop_button.configure(state='normal' if self.active else 'disabled')

    def add_folder(self):
        folder = filedialog.askdirectory(parent=self.window, title='Carpeta con salidas de Conocimientos')
        if folder:
            path = Path(folder).resolve()
            if path not in self.roots:
                self.roots.append(path)
            self.external_roots = list(self.roots)
            self._roots_label()
            self.refresh_catalog()

    def clear_folders(self):
        self.roots.clear()
        self.external_roots.clear()
        self.sources.clear()
        self.selected.clear()
        self.period_choices.clear()
        self.period_keys.clear()
        self.catalog.clear()
        self.loaded_paths.clear()
        self.table.delete(*self.table.get_children())
        self.period_table.delete(*self.period_table.get_children())
        self.update_filter_options()
        self.render_periods()
        self.scan_errors = []
        self.catalog_errors = []
        self._roots_label()
        self.status.set('Agrega una carpeta para cargar sus datos.')
        self._buttons()

    def _launch(self, name, work):
        if self.active:
            return
        self.active = True
        self.stop.clear()
        self._buttons()
        self.bar.configure(value=0)

        def worker():
            try:
                self.events.put((name, work()))
            except BuildCancelled as exc:
                self.events.put(('cancelled', {'message': str(exc), 'audit': getattr(exc, 'audit', None)}))
            except Exception as exc:
                self.events.put(('error', {'message': str(exc), 'audit': getattr(exc, 'audit', None)}))
            finally:
                self.events.put(('idle', None))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_catalog(self):
        if self.active:
            return
        roots = list(self.roots)
        include_history = self.include_history.get()
        self.status.set('Buscando archivos…')
        self.loaded_paths.clear()
        self.sources.clear()
        self.selected.clear()
        self.table.delete(*self.table.get_children())
        self.period_table.delete(*self.period_table.get_children())
        self.period_keys.clear()
        self.render_periods()
        self._launch('catalog_done', lambda: catalog_sources(roots, self.stop, include_history))

    def month_number(self):
        value = self.month.get()
        return None if value == 'Todos' else (int(value) if value.isdigit() else MONTH_LABELS.index(value)+1)

    def requested_candidates(self):
        return choose_candidates(self.catalog,
            year=None if self.year.get() == 'Todos' else int(self.year.get()),
            month=self.month_number(),
            mode=MODES[self.mode.get()], kind=INPUT_KINDS[self.input_kind.get()])

    def ready_to_build(self):
        requested = {c.path for c in self.requested_candidates()}
        return bool(self.chosen_periods()) and bool(requested) and requested <= self.loaded_paths

    def scan(self):
        if self.active:
            return
        candidates = self.requested_candidates()
        if not candidates:
            self.status.set('No hay archivos con esos filtros.')
            return
        paths = [c.path for c in candidates]
        include_history = self.include_history.get()
        self.status.set(f'Cargando {len(paths)} archivos de la selección…')
        self.loaded_paths = set()
        self._scan_paths = set(paths)
        self._launch('scan_done', lambda: discover_sources(paths, self.stop,
            lambda e: self.events.put(('progress', e)), include_history=include_history))

    def select_all(self, value):
        if self.active:
            return
        for key in self.sources:
            self.selected[key] = value
            self.table.set(key, 'use', 'Sí' if value else 'No')
        self.render_periods()
        self._buttons()

    def toggle(self, event):
        if not self.active and self.table.identify_column(event.x) == '#1':
            key = self.table.identify_row(event.y)
            if key:
                self.selected[key] = not self.selected[key]
                self.table.set(key, 'use', 'Sí' if self.selected[key] else 'No')
                self.render_periods()
                self._buttons()

    def toggle_selected(self, event):
        if not self.active:
            for key in self.table.selection():
                self.selected[key] = not self.selected[key]
                self.table.set(key, 'use', 'Sí' if self.selected[key] else 'No')
            self.render_periods()
            self._buttons()
        return 'break'

    def update_filter_options(self):
        keys = set(available_periods(self.sources.values()))
        keys.update((candidate.period, candidate.mode) for candidate in self.catalog
                    if candidate.period and candidate.mode)
        years = sorted({period[:4] for period, mode in keys})
        if not keys and any(not c.period for c in self.catalog):
            from datetime import datetime
            years = [str(y) for y in range(datetime.now().year + 1, 1999, -1)]
        modes = [label for label, mode in MODES.items() if mode and any(key[1] == mode for key in keys)]
        if not keys and self.catalog:
            modes = list(MODE_LABELS.values())
        for widget, var, values in ((self.filters[0], self.year, ['Todos'] + years),
                                    (self.filters[2], self.mode, ['Todas'] + modes)):
            widget.configure(values=values)
            if var.get() not in values:
                var.set(values[0])
        months = sorted({period[5:] for period, mode in keys
            if (self.year.get() == 'Todos' or period[:4] == self.year.get())
            and (MODES[self.mode.get()] is None or mode == MODES[self.mode.get()])})
        values = ['Todos'] + [MONTH_LABELS[int(month)-1] for month in months]
        if not keys and self.catalog:
            values = ['Todos'] + MONTH_LABELS
        self.filters[1].configure(values=values)
        if self.month.get() not in values:
            self.month.set('Todos')

    def visible_period(self, key):
        period, mode = key
        return ((self.year.get() == 'Todos' or period[:4] == self.year.get()) and
                (self.month_number() is None or int(period[5:]) == self.month_number()) and
                (MODES[self.mode.get()] is None or mode == MODES[self.mode.get()]))

    def chosen_periods(self):
        chosen_sources = {source.key for key, source in self.sources.items() if self.selected[key]}
        return {key for key, entries in available_periods(self.sources.values()).items()
                if self.period_choices.get(key, False) and self.visible_period(key)
                and any(source.key in chosen_sources and period.rows > 0 for source, period in entries)}

    def render_periods(self):
        highlighted = {self.period_keys[item] for item in self.period_table.selection() if item in self.period_keys}
        focused = self.period_keys.get(self.period_table.focus())
        scroll = self.period_table.yview()[0]
        self.period_table.delete(*self.period_table.get_children())
        self.period_keys.clear()
        chosen_sources = {source.key for key, source in self.sources.items() if self.selected[key]}
        groups = available_periods(self.sources.values())
        for index, (key, entries) in enumerate(groups.items()):
            if not self.visible_period(key):
                continue
            active = [(source, period) for source, period in entries if source.key in chosen_sources and period.rows > 0]
            self.period_choices.setdefault(key, bool(active))
            tracked = [period for source, period in entries if period.pending is not None]
            if any(period.pending for period in tracked):
                if len(tracked) == 1:
                    state = f'{tracked[0].saved} guardados · {tracked[0].pending} pendientes'
                else:
                    state = f'{sum(bool(p.pending) for p in tracked)} archivos con pendientes'
            elif tracked:
                state = 'Sin pendientes en la selección'
            else:
                state = 'Estado no disponible'
            if not active:
                state = 'Sin datos elegidos'
            item = str(index)
            self.period_keys[item] = key
            self.period_table.insert('', 'end', iid=item, values=(
                ('Sí' if self.period_choices[key] else 'No') if active else '—',
                f'{MONTH_LABELS[int(key[0][5:])-1]} {key[0][:4]}', MODE_LABELS[key[1]],
                len(active), state), tags=() if active else ('unavailable',))
            if key in highlighted:
                self.period_table.selection_add(item)
            if key == focused:
                self.period_table.focus(item)
        self.period_table.yview_moveto(scroll)
        self.period_summary.set(f'{len(self.chosen_periods())} mes(es) seleccionados' if groups else 'Sin datos cargados')
        if self.period_keys:
            self.empty_hint.place_forget()
        else:
            self.empty_hint.configure(text='No hay meses con estos filtros.' if self.sources else
                'Elige los filtros y pulsa Cargar datos.')
            self.empty_hint.place(relx=.5, rely=.5, anchor='center')

    def filter_changed(self, event=None):
        self.update_filter_options()
        self.render_periods()
        self.suggest_output()
        self._buttons()
        if not self.active and not self.ready_to_build():
            self.status.set('Pulsa Cargar datos para esta selección.')

    def select_periods(self, value):
        if self.active:
            return
        for key in self.period_keys.values():
            self.period_choices[key] = value
        self.render_periods()
        self.suggest_output()
        self._buttons()

    def toggle_period(self, event):
        if not self.active and self.period_table.identify_column(event.x) == '#1':
            item = self.period_table.identify_row(event.y)
            if item:
                self._toggle_period_items([item])

    def toggle_selected_periods(self, event):
        if not self.active:
            self._toggle_period_items(self.period_table.selection())
        return 'break'

    def _toggle_period_items(self, items):
        for item in items:
            if self.period_table.set(item, 'use') != '—':
                key = self.period_keys[item]
                self.period_choices[key] = not self.period_choices[key]
        self.render_periods()
        self.suggest_output()
        self._buttons()

    def suggest_output(self, event=None):
        mode = MODES[self.mode.get()] or 'todos'
        suffix = '_' + mode
        if self.year.get() != 'Todos':
            suffix += '_' + self.year.get()
        if self.month.get() != 'Todos':
            suffix += f'_{self.month_number():02d}'
        count = len(self.chosen_periods())
        if count > 1:
            suffix += f'_{count}_periodos'
        current = Path(self.output.get())
        self.output.set(str(current.parent / f'Bls_sin_courier{suffix}{OUTPUT_CHOICES[self.output_format.get()]}'))

    def _output_path_changed(self, *args):
        kind = OUTPUT_FORMATS.get(Path(self.output.get()).suffix.lower())
        if kind:
            self.output_format.set('SQLite (.sqlite3)' if kind=='SQLite' else 'Excel (.xlsx)')

    def output_format_changed(self, event=None):
        self.output.set(str(Path(self.output.get()).with_suffix(OUTPUT_CHOICES[self.output_format.get()])))

    def choose_output(self):
        extension = OUTPUT_CHOICES[self.output_format.get()]
        path = filedialog.asksaveasfilename(parent=self.window, title='Guardar base para BLs_BOT',
            defaultextension=extension,
            filetypes=[('Excel','*.xlsx')] if extension=='.xlsx' else [('SQLite','*.sqlite3 *.sqlite *.db')],
            initialdir=str(Path(self.output.get()).parent), initialfile=Path(self.output.get()).name)
        if path:
            self.output.set(path)

    def generate(self):
        if not self.ready_to_build():
            messagebox.showwarning('Cargar datos', 'Cargue los datos de la selección antes de generar la base.', parent=self.window)
            return
        periods = self.chosen_periods()
        sources = [source for key, source in self.sources.items() if self.selected[key]
                   and any(period.key in periods and period.rows > 0 for period in source.periods)]
        if not sources:
            messagebox.showwarning('Períodos', 'Marque al menos un período y una fuente con datos.', parent=self.window)
            return
        destination = Path(self.output.get()).expanduser().resolve()
        if destination.exists() and not messagebox.askyesno('Archivo existente', f'¿Sustituir {destination.name}?', parent=self.window):
            return
        filters = {'year': None if self.year.get() == 'Todos' else int(self.year.get()),
                   'month': self.month_number(),
                   'mode': MODES[self.mode.get()], 'periods': periods}
        self.status.set('Preparando la base…')
        self._launch('build_done', lambda: build_base(sources, destination, **filters, stop=self.stop,
                      progress=lambda e: self.events.put(('progress', e))))

    def poll(self):
        self.poll_id = None
        while True:
            try:
                kind, data = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                self.bar.configure(maximum=max(1, data['total']), value=data['current'])
                phase = data['phase']
                if phase == 'scan':
                    detail = f" · {data['rows']:,} filas revisadas" if data.get('rows') is not None else ''
                    self.status.set(f"Cargando {data['current']}/{data['total']}: {Path(data['file']).name}{detail}")
                elif phase == 'read':
                    self.status.set(f"Leyendo {data['current']}/{data['total']} · {data['read']:,} conocimientos")
                else:
                    self.status.set(f"Escribiendo {data.get('format','Excel')}: {data['exported']:,}/{data['total']:,} BL")
            elif kind == 'catalog_done':
                self.catalog, self.catalog_errors = data
                self.scan_errors = list(self.catalog_errors)
                self.update_filter_options()
                self.render_periods()
                self.status.set(f'{len(self.catalog)} archivos disponibles · selecciona los filtros y carga los datos.')
            elif kind == 'scan_done':
                sources, self.scan_errors = data
                self.scan_errors = self.catalog_errors + self.scan_errors
                unreadable = {Path(path).resolve() for path, reason in self.scan_errors}
                self.loaded_paths = self._scan_paths - unreadable
                choices = {source.key: self.selected.get(key, True) for key, source in self.sources.items()}
                self.sources, self.selected = {}, {}
                defaults = default_selection(sources)
                self.table.delete(*self.table.get_children())
                for index, source in enumerate(sources):
                    key = str(index)
                    self.sources[key] = source
                    self.selected[key] = choices.get(source.key, defaults[source.key])
                    self.table.insert('', 'end', iid=key, values=('Sí' if self.selected[key] else 'No', source.period or 'Por fila',
                        source.mode or 'Por fila', source.kind, source.rows if source.rows is not None else 'Con datos',
                        str(source.path) + (f' [{source.sheet}]' if source.sheet else '')))
                self.update_filter_options()
                self.render_periods()
                self.tabs.select(self.months_tab)
                self.status.set(f'{len(sources)} archivos cargados · elige los meses.' +
                                (f' {len(self.scan_errors)} errores (Diagnóstico).' if self.scan_errors else ''))
            elif kind == 'build_done':
                self.last_audit = data['audit']
                self.bar.configure(maximum=1, value=1)
                self.status.set(f"Base lista · {data['exported']:,} BL · {data.get('format','Excel')}")
                details = ''
                if data['invalid'] or data['conflicts']:
                    details += f"\n{data['invalid']:,} filas inválidas y {data['conflicts']:,} conflictos excluidos. Revisa Diagnóstico."
                if data['numeric_bl']:
                    details += f"\n{data['numeric_bl']:,} BL numéricos sin máscara: se conservó el valor disponible."
                messagebox.showinfo('Base creada', f"{data['exported']:,} BL guardados.\n\n{data['output']}" + details,
                    parent=self.window)
            elif kind in ('error', 'cancelled'):
                self.status.set(data['message'])
                if data.get('audit'):
                    self.last_audit = data['audit']
                if kind == 'error':
                    messagebox.showerror('Base de BLS', data['message'], parent=self.window)
            elif kind == 'idle':
                self.active = False
                self._buttons()
                if self.after_close:
                    callback = self.after_close
                    self.destroy()
                    callback()
                    return
        if self.window.winfo_exists():
            self.poll_id = self.window.after(100, self.poll)

    def diagnostics(self):
        import sqlite3
        dialog = ttk.Toplevel(self.window)
        dialog.title('Diagnóstico de base BLS')
        dialog.geometry('1000x430')
        table = ttk.Treeview(dialog, columns=('file', 'row', 'reason'), show='headings')
        for column, title, width in [('file', 'Fuente', 410), ('row', 'Fila', 60), ('reason', 'Motivo', 500)]:
            table.heading(column, text=title)
            table.column(column, width=width)
        scroll = ttk.Scrollbar(dialog, command=table.yview)
        scroll.pack(side='right', fill='y')
        table.configure(yscrollcommand=scroll.set)
        table.pack(fill='both', expand=True)
        for path, reason in self.scan_errors:
            table.insert('', 'end', values=(path, '', reason))
        if self.last_audit:
            db = sqlite3.connect(Path(self.last_audit).as_uri() + '?mode=ro', uri=True)
            try:
                for row in db.execute('''SELECT s.path || CASE WHEN s.sheet='' THEN '' ELSE ' [' || s.sheet || ']' END,
                        i.row_number,i.reason FROM issues i JOIN sources s ON s.id=i.source_id LIMIT 1000'''):
                    table.insert('', 'end', values=row)
            finally:
                db.close()
        ttk.Label(dialog, text='Se muestran hasta 1000 incidencias; el diagnóstico completo se conserva en SQLite.', padding=8).pack(fill='x')

    def open_output(self):
        folder = Path(self.output.get()).expanduser().resolve().parent
        folder.mkdir(parents=True, exist_ok=True)
        os.startfile(folder)

    def close(self, after_close=None):
        if self.active:
            self.stop.set()
            self.after_close = after_close or (lambda: None)
            self.status.set('Deteniendo; se conserva el archivo de salida anterior…')
        else:
            self.destroy()
            if after_close:
                after_close()

    def destroy(self):
        if self.output_trace_id is not None:
            self.output.trace_remove('write',self.output_trace_id)
            self.output_trace_id = None
        if self.poll_id is not None:
            self.window.after_cancel(self.poll_id)
            self.poll_id = None
        self.window.destroy()

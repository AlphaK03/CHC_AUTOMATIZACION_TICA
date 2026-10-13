"""Vista de progreso; Tk solo se actualiza desde su hilo principal."""
import asyncio
import queue
import threading
from pathlib import Path
from tkinter import messagebox

import ttkbootstrap as ttk

from conocimientos import KnowledgeStore, DEFAULT_CONCURRENCY, MAX_CONCURRENCY, validate_concurrency
from utils import load_config
from resultados import failure_csv_path


class KnowledgeProgressWindow:
    def __init__(self, parent, runner, modes, month, year, on_finished=None, flow='conocimientos'):
        self.window = ttk.Toplevel(parent)
        labels = {'conocimientos': 'Conocimientos', 'duas': 'DUAs por manifiesto', 'movimientos': 'Movimientos'}
        self.window.title(labels[flow] + ' — descarga y pendientes')
        self.flow = flow
        self.window.geometry('1180x590')
        self.runner, self.args = runner, (modes, month, year)
        self.on_finished = on_finished
        self.events = queue.Queue()
        self.active = False
        self.loop = self.task = None
        self.stop_requested = threading.Event()
        self.after_close = None
        self.closing = False
        self.databases, self.progress_by_db = set(), {}
        self.concurrency = ttk.StringVar(value=str(load_config().get(flow + '_concurrencia', DEFAULT_CONCURRENCY if flow == 'conocimientos' else 4)))
        self.auto_export = ttk.BooleanVar(value=True)
        self.status = ttk.StringVar(value='Configure las descargas simultáneas y pulse Iniciar descarga.')

        controls = ttk.Frame(self.window, padding=10)
        controls.pack(fill='x')
        ttk.Label(controls, text='Descargas simultáneas:').pack(side='left')
        self.spinner = ttk.Spinbox(controls, from_=1, to=MAX_CONCURRENCY, textvariable=self.concurrency, width=4)
        self.spinner.pack(side='left', padx=8)
        self.export_check = ttk.Checkbutton(controls, text='Exportar CSV al terminar', variable=self.auto_export)
        self.export_check.pack(side='left', padx=10)
        self.start_button = ttk.Button(controls, text='Iniciar descarga', command=self.start)
        self.start_button.pack(side='right', padx=4)
        self.stop_button = ttk.Button(controls, text='Detener', command=self.stop)
        self.stop_button.pack(side='right', padx=4)
        self.export_button = ttk.Button(controls, text='Exportar SQLite a CSV', command=self.export)
        self.export_button.pack(side='right', padx=4)
        ttk.Label(self.window, textvariable=self.status, padding=10).pack(fill='x')
        self.bar = ttk.Progressbar(self.window, maximum=1)
        self.bar.pack(fill='x', padx=10, pady=(0, 8))
        frame = ttk.Frame(self.window, padding=10)
        frame.pack(fill='both', expand=True)
        columns = ('fila', 'id', 'estado', 'intentos', 'paginas', 'leidos', 'guardados', 'error')
        self.table = ttk.Treeview(frame, columns=columns, show='headings')
        for col, title, width in zip(columns,
                ('Fila', 'Manifiesto', 'Estado', 'Intentos', 'Páginas', 'Leídos', 'Guardados', 'Actividad / último error'),
                (55, 280, 110, 65, 65, 75, 80, 310)):
            self.table.heading(col, text=title)
            self.table.column(col, width=width, minwidth=45, stretch=col in ('id', 'error'))
        scrollbar = ttk.Scrollbar(frame, orient='vertical', command=self.table.yview)
        self.table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.table.pack(side='left', fill='both', expand=True)
        self.table.tag_configure('Guardado', foreground='#27864a')
        self.table.tag_configure('Pendiente', foreground='#c77b16')
        self.table.tag_configure('Descargando', foreground='#2685c2')
        self.table.tag_configure('Excluido', foreground='#b33a3a')
        self.window.protocol('WM_DELETE_WINDOW', self.close)
        self.window.after(100, self.poll)
        self._buttons()

    def _buttons(self):
        for widget in (self.spinner, self.export_check, self.start_button, self.export_button):
            widget.configure(state='disabled' if self.active else 'normal')
        self.stop_button.configure(state='normal' if self.active else 'disabled')

    def start(self):
        if self.active:
            return
        try:
            concurrency = validate_concurrency(self.concurrency.get())
        except ValueError as exc:
            messagebox.showerror('Concurrencia', str(exc), parent=self.window)
            return
        overrides = {self.flow + '_concurrencia': concurrency,
                     self.flow + '_exportar_csv': self.auto_export.get(),
                     self.flow + '_progress_callback': lambda event: self.events.put(('progress', event))}
        self.progress_by_db.clear()
        self.start_button.configure(text='Reintentar pendientes')
        self._launch(lambda: self.runner(*self.args, config_overrides=overrides))

    def _launch(self, coroutine):
        self.active = True
        self.stop_requested.clear()
        self.status.set('Consultando selección y recuperando el avance de SQLite…')
        self._buttons()

        def work():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self.loop = loop
            task = loop.create_task(coroutine())
            self.task = task
            if self.stop_requested.is_set():
                task.cancel()
            result = 'Finalizado. Revise los guardados, pendientes y excluidos.'
            try:
                loop.run_until_complete(task)
            except asyncio.CancelledError:
                result = 'Detenido. El avance está en SQLite; las filas sin terminar siguen pendientes.'
            except Exception as exc:
                result = f'Error: {exc}. El avance confirmado permanece en SQLite.'
            finally:
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.run_until_complete(loop.shutdown_default_executor())
                loop.close()
                self.loop = self.task = None
                self.events.put(('done', result))

        threading.Thread(target=work, name=self.flow, daemon=False).start()

    def stop(self):
        self.stop_requested.set()
        if self.loop and self.task:
            try:
                self.loop.call_soon_threadsafe(self.task.cancel)
            except RuntimeError:
                pass
        self.status.set('Deteniendo y cerrando conexiones; conservando pendientes…')

    def _row(self, database, job):
        iid = database + '|' + job['id']
        values = (job['ordinal'], job['id'], job['state'], job['attempts'], job['pages'],
                  job['read'], job['kept'] if job['state'] == 'Guardado' else '', job['error'])
        if self.table.exists(iid):
            self.table.item(iid, values=values, tags=(job['state'],))
        else:
            self.table.insert('', 'end', iid=iid, values=values, tags=(job['state'],))

    def _progress(self, event):
        database = event['database']
        self.databases.add(database)
        self.progress_by_db[database] = event['progress']
        for job in event.get('jobs', []):
            self._row(database, job)
        if 'job' in event:
            self._row(database, event['job'])
        totals = {k: sum(p[k] for p in self.progress_by_db.values())
                  for k in ('selected', 'saved', 'pending', 'active', 'processed_run')}
        accounted = sum(p.get('accounted', p['saved']) for p in self.progress_by_db.values())
        excluded = sum(p.get('excluded', 0) for p in self.progress_by_db.values())
        exclusion_status = f'Excluidos: {excluded} | ' if self.flow == 'duas' else ''
        self.status.set(f"Seleccionados: {totals['selected']} | Guardados: {totals['saved']} | "
                        f"{exclusion_status}"
                        f"Pendientes: {totals['pending']} | Descargando: {totals['active']} | "
                        f"Contabilizados: {accounted}/{totals['selected']} | "
                        f"Intentados esta ejecución: {totals['processed_run']}")
        self.bar.configure(maximum=max(1, totals['selected']), value=accounted)

    def poll(self):
        for _ in range(300):
            try:
                kind, event = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == 'progress':
                self._progress(event)
            elif kind == 'done':
                self.active = False
                self._buttons()
                if event.startswith(('Error:', 'Detenido')) or not self.progress_by_db:
                    self.status.set(event)
                if self.on_finished:
                    self.on_finished(event)
                if self.closing:
                    self.window.destroy()
                    if self.after_close:
                        self.after_close()
                    return
        self.window.after(100, self.poll)

    def export(self):
        if self.active or not self.databases:
            return

        async def export_all():
            for database in sorted(self.databases):
                store = KnowledgeStore.open_existing(database)
                try:
                    failed = failure_csv_path(store.csv_path)
                    store.export(failed)
                finally:
                    store.close()
        self._launch(export_all)

    def close(self, after_close=None):
        if self.active:
            self.closing = True
            self.after_close = after_close
            self.stop()
        else:
            self.window.destroy()
            if after_close:
                after_close()

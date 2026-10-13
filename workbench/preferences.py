"""Preferencias locales del Workbench, independientes de los motores."""
import json
import os
from pathlib import Path
import tempfile

from PySide6.QtCore import QObject, Property, Signal, Slot


class Preferences(QObject):
    changed = Signal()
    error = Signal(str)

    def __init__(self, path: Path, persist=True):
        super().__init__()
        self.path = path
        self.persist = persist
        try:
            self.values = json.loads(path.read_text(encoding='utf-8')) if persist else {}
        except (OSError, ValueError):
            self.values = {}

    @Property(bool, notify=changed)
    def dark(self): return bool(self.values.get('dark', True))

    @Slot(bool)
    def setDark(self, value):
        self.values['dark'] = value
        if self.persist:
            temporary = None
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
                with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                    json.dump(self.values, stream)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, self.path)
            except OSError as error:
                self.error.emit(f'No se pudo guardar la apariencia: {error}')
            finally:
                if temporary and os.path.exists(temporary):
                    os.unlink(temporary)
        self.changed.emit()

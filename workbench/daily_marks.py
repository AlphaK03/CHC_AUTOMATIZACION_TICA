"""Aceptación manual de días para calendario y bitácora, sin cambiar los motores."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile


class DailyMarks:
    def __init__(self, root):
        self.path = Path(root) / 'data' / 'daily' / 'manual_completed_days.json'
        self.values = {}
        self.error = ''
        try:
            values = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(values, dict):
                raise ValueError('El archivo de marcas no contiene un objeto JSON.')
            self.values = values
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            self.error = str(error)

    def set_completed(self, day, enabled):
        if self.error:
            raise ValueError('No se pudieron leer las marcas existentes: ' + self.error)
        values = dict(self.values)
        if enabled:
            values[day] = datetime.now(timezone.utc).isoformat()
        else:
            values.pop(day, None)
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary = tempfile.mkstemp(dir=self.path.parent, suffix='.tmp')
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(values, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        self.values = values

"""Bloqueos SQLite reales en el protocolo: lector diferido y motor intacto."""
from contextlib import closing
from pathlib import Path
from threading import Event
from unittest.mock import patch
import json
import sqlite3
import tempfile
import unittest

from chc_runtime import worker


class ViewContentionTests(unittest.TestCase):
    def run_requests(self, *, background=True, locked=True, sql='SELECT value FROM saved'):
        events = []
        started, first, second = Event(), Event(), Event()
        stop = Event()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'jobs.sqlite3'
            with closing(sqlite3.connect(path)) as writer:
                writer.execute('CREATE TABLE saved(value TEXT)')
                writer.execute("INSERT INTO saved VALUES ('confirmado')")
                writer.commit()
                if locked:
                    writer.execute('BEGIN EXCLUSIVE')
                    writer.execute("UPDATE saved SET value='sin confirmar'")

                class Service:
                    stop_event = stop
                    def execute(self, command, request):
                        if command == 'run':
                            started.set()
                            if not stop.wait(5):
                                raise TimeoutError('El fixture no recibió Detener')
                            return {'runStatus':'stopped'}
                        with closing(sqlite3.connect(path.as_uri()+'?mode=ro', uri=True, timeout=.05)) as reader:
                            return {'view':{'rows':reader.execute(sql).fetchall()}}
                    def snapshot(self): return {}
                    def view(self, request): return {}

                class Protocol:
                    def emit(self, event, **data):
                        events.append(dict(event=event, **data))
                        if event == 'idle' and data.get('requestId') == 2: first.set()
                        if event == 'idle' and data.get('requestId') == 3: second.set()

                def requests():
                    try:
                        if background:
                            yield json.dumps(dict(command='run',requestId=1))
                            self.assertTrue(started.wait(3))
                        yield json.dumps(dict(command='view',requestId=2))
                        self.assertTrue(first.wait(3))
                        if locked and background:
                            self.assertFalse(stop.is_set())
                            writer.rollback()
                            yield json.dumps(dict(command='view',requestId=3))
                            self.assertTrue(second.wait(3))
                        yield json.dumps(dict(command='stop'))
                        yield json.dumps(dict(command='shutdown'))
                    finally:
                        stop.set()
                        writer.rollback()

                class Input:
                    def reconfigure(self, **kwargs): pass
                    def __iter__(self): return requests()

                with patch.object(worker,'load_profile',return_value={}), \
                        patch.object(worker,'DetailsService',return_value=Service()), \
                        patch.object(worker,'Protocol',Protocol), \
                        patch.object(worker.sys,'argv',['worker','--storage-root',folder]), \
                        patch.object(worker.sys,'stdin',Input()), \
                        patch.object(worker.logging,'exception'):
                    self.assertEqual(worker.main(),0)
        return events

    def test_busy_background_view_keeps_operation_alive_then_reads_committed_result(self):
        events = self.run_requests()
        self.assertEqual(len([e for e in events if e['event']=='view_deferred']),1)
        self.assertFalse([e for e in events if e['event']=='error'])
        idle = next(e for e in events if e['event']=='idle' and e['requestId']==2)
        self.assertTrue(idle['readonly'])
        loaded = next(e for e in events if e['event']=='result' and e['requestId']==3)
        self.assertEqual(loaded['view']['rows'],[('confirmado',)])
        self.assertEqual(next(e for e in events if e['event']=='result' and e['command']=='run')['runStatus'],'stopped')

    def test_foreground_lock_and_other_read_failures_remain_errors(self):
        for values in (dict(background=False),dict(locked=False,sql='SELECT value FROM missing')):
            with self.subTest(values=values):
                events = self.run_requests(**values)
                self.assertFalse([e for e in events if e['event']=='view_deferred'])
                self.assertTrue([e for e in events if e['event']=='error'])


if __name__ == '__main__': unittest.main()

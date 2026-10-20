"""Lectores sin respuesta y recuperación; sin consultas de red."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_details_bridge import APP, wait_until
from batch_bridge import BatchChannel
from PySide6.QtCore import QProcess


class BatchLoadingTimeoutTests(unittest.TestCase):
    def test_stalled_reader_exits_and_can_reconnect_without_touching_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            marker = root/'confirmed.csv'
            marker.write_bytes(b'ID,valor\n00001,12\n')
            channel = BatchChannel('manifiestos','conocimientos',root)
            # Proceso de prueba que conserva stdin abierto y nunca contesta.
            channel.process.start(sys.executable, ['-u','-c','import sys; sys.stdin.buffer.read()'])
            wait_until(lambda: channel.process.state()==QProcess.Running)
            channel.ready = True
            channel.load_timer.setInterval(100)
            self.assertTrue(channel.send('refresh'))
            wait_until(lambda: channel.process.state()==QProcess.NotRunning)
            self.assertFalse(channel.busy)
            self.assertTrue(channel._load_expired)
            self.assertIn('Reconectar', channel.error)
            self.assertIsNone(channel.pending)
            self.assertEqual(marker.read_bytes(), b'ID,valor\n00001,12\n')
            channel.load_timer.setInterval(60000)
            try:
                self.assertTrue(channel.send('refresh'))
                wait_until(lambda: channel.ready and not channel.busy or bool(channel.error))
                self.assertTrue(channel.ready, channel.error)
                self.assertFalse(channel.error)
                self.assertFalse(channel._load_expired)
                self.assertFalse(channel.load_timer.isActive())
            finally:
                channel.shutdown()
                wait_until(lambda: channel.process.state()==QProcess.NotRunning)

    def test_deadline_never_terminates_downloads_or_writers(self):
        with tempfile.TemporaryDirectory() as folder:
            channel = BatchChannel('manifiestos','duas',Path(folder))
            channel.busy = True
            for command in ('run','retry_empty','export','import_progress','base_load','base_build','knowledge_build'):
                channel.active_command = command
                with patch.object(channel,'force_close') as close:
                    channel.load_timeout()
                close.assert_not_called()
                self.assertFalse(channel.error)
            channel.active_command='refresh'
            channel.closing=True
            with patch.object(channel,'force_close') as close:
                channel.load_timeout()
            close.assert_not_called()


if __name__=='__main__':
    unittest.main()

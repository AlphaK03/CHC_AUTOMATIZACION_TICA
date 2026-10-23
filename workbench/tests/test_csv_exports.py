"""Acción conjunta explícita: sin consultas, selección ni interrupciones."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP, wait_until
from PySide6.QtCore import QObject, Signal, QTimer
from csv_exports import CsvExports


class Endpoint(QObject):
    eventReceived=Signal('QVariantMap')
    changed=Signal()
    enabled=ready=True
    busy=closing=dailyActive=False
    error=''
    def __init__(self, fail=False):
        super().__init__();self.calls=[];self.fail=fail
    def _send(self, command, data):
        self.calls.append((command,data));self.busy=True
        def done():
            self.busy=False
            self.eventReceived.emit({'event':'result','command':command,'exportReport':{
                'token':data['exportToken'],'exported':0 if self.fail else 2,
                'errors':['CSV ocupado'] if self.fail else []}})
        QTimer.singleShot(0,done)
        return True


class CsvExportTests(unittest.TestCase):
    def test_only_explicit_action_exports_and_busy_module_is_preserved(self):
        one=Endpoint();busy=Endpoint();busy.busy=True;bad=Endpoint(fail=True)
        controller=CsvExports({'uno':one,'ocupado':busy,'fallo':bad})
        APP.processEvents();self.assertEqual(one.calls,[])
        controller.generateAll();wait_until(lambda:not controller.busy)
        self.assertEqual([c[0] for c in one.calls],['export_all'])
        self.assertEqual(busy.calls,[]);self.assertTrue(busy.busy)
        self.assertEqual(controller.exported,2)
        self.assertEqual(len(controller.errors),2)
        self.assertIn('CSV ocupado',controller.message)

    def test_cancel_and_late_response_do_not_start_another_export(self):
        one=Endpoint();two=Endpoint();controller=CsvExports({'uno':one,'dos':two})
        controller.generateAll();controller.cancel();APP.processEvents()
        self.assertFalse(controller.busy);self.assertEqual(two.calls,[])

    def test_other_tokens_cannot_finish_current_export(self):
        one=Endpoint();controller=CsvExports({'uno':one})
        controller.generateAll()
        controller.receive({'event':'result','command':'export_all','exportReport':{'token':'old','exported':99,'errors':[]}})
        self.assertTrue(controller.busy)
        wait_until(lambda:not controller.busy)
        self.assertEqual(controller.exported,2)


if __name__=='__main__':unittest.main()

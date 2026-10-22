"""Reconsulta explícita del lote elegido; datos, workers y portales aislados."""
from contextlib import closing
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP,wait_until,DetailsBridge,DemoBackend,Preferences
from batch_bridge import BatchBridge
from chc_runtime.job_store import RunLock
from PySide6.QtCore import QObject,QMetaObject,QUrl,Qt
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtGui import QFontDatabase

ROOT=Path(__file__).resolve().parents[2]
SEED=r'''
import sys,json
from pathlib import Path
from threading import Event
repo,root=Path(sys.argv[1]),Path(sys.argv[2])
sys.path.insert(0,str(repo));sys.path.insert(0,str(repo/'bots/bls/src'))
import pandas as pd
from config_manager import DEFAULTS
from core.inputs import batch_scope
from core.store import JobStore
from chc_runtime.manifest_service import BatchService
rows=[dict(IDManifiesto='4-1-0002601287L-P001-13/10/26',**{'Secuencia Tica':str(n),
      'BL original':'000000'+str(n),'Fecha Manifiesto':'13/10/2026','Mes':'2026-10'}) for n in range(1,4)]
base=root/'base.xlsx'
pd.DataFrame(rows).to_excel(base,index=False,sheet_name='BLS')
service=BatchService(root,'bls',lambda *a,**k:None,Event())
service.index['config'].update(input=str(base),inputMode='knowledge',name='Octubre prueba',workers=1,max_retries=2)
record=service.prepare()
from input_files import load_input_file
frame=load_input_file(base,'BLS')
signature,scope=batch_scope(frame,{**DEFAULTS,'sheet_name':'BLS'})
scope['revision']=''
store=JobStore(Path(record['work'])/'BLS'/signature[:16]/'SQLite/bls.sqlite3',signature,scope)
try:
 store.prepare(frame);store.start_run()
 for key,ordinal,payload in store.pending():
  token=store.claim(key)
  if ordinal==3:store.fail(key,token,'Pendiente anterior','transient')
  else:store.save(key,token,['BL','Aduana','manifiesto','bls'],[] if ordinal==1 else
                  [[payload['BL original'],'013',payload['IDManifiesto'],payload['BL original']]])
 store.finish_run(stopped=True)
finally:store.close()
record['state']='Detenido';service.inspect();service.save();service.export()
'''


def seed(root):
    subprocess.run([str(ROOT/'bots/bls/.venv/Scripts/python.exe'),'-c',SEED,str(ROOT),str(root)],cwd=ROOT,check=True)
    return next(root.glob('data/jobs/bls/**/SQLite/bls.sqlite3'))


class EmptyRetryTests(unittest.TestCase):
    def test_qml_confirmation_count_action_and_compact_capture(self):
        if sys.platform=='win32':
            for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','consola.ttf'):
                QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);seed(root)
            bridge=BatchBridge(module_id='bls',storage_root=root,knowledge_root=root/'no_sources',offline_fixture=True)
            manifests=BatchBridge(enabled=False,storage_root=root/'manifiestos')
            old=[DetailsBridge(enabled=False,module_id=m) for m in ('detalles','duas_transito','talon','xmovimientos')]
            here=ROOT/'workbench'
            backend=DemoBackend(here/'modules.json',*old,manifests,bridge)
            preferences=Preferences(root/'prefs.json',persist=False)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=old[0],transit=old[1],talon=old[2],movements=old[3],
                                   manifests=manifests,bls=bridge,preferences=preferences).items():
                engine.rootContext().setContextProperty(name,value)
            window=None
            def find(name):
                target=window.findChild(QObject,name)
                if target:return target
                pending=[window.contentItem()]
                while pending:
                    item=pending.pop()
                    if item.objectName()==name:return item
                    pending.extend(item.childItems())
            try:
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                backend.navigate('bls');engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
                self.assertTrue(engine.rootObjects(),warnings)
                window=engine.rootObjects()[0];window.resize(1000,600);APP.processEvents()
                action=find('blsRetryEmpty');self.assertTrue(action.property('enabled'))
                self.assertTrue(QMetaObject.invokeMethod(action,'triggered',Qt.DirectConnection))
                dialog=find('blsEmptyRetryDialog');wait_until(lambda:dialog.property('visible'))
                self.assertEqual(dialog.property('count'),1)
                self.assertEqual(dialog.property('recordId'),bridge.activeId)
                button=find('blsConfirmRetryEmpty');self.assertTrue(button.property('enabled'))
                capture=ROOT/'runtime/diagnostics/bls-empty-retry.png';capture.parent.mkdir(parents=True,exist_ok=True)
                APP.processEvents();self.assertTrue(window.grabWindow().save(str(capture)))
                self.assertLessEqual(dialog.property('width'),window.width())
                self.assertLessEqual(dialog.property('height'),window.height())
                self.assertTrue(QMetaObject.invokeMethod(button,'clicked',Qt.DirectConnection))
                wait_until(lambda:not bridge.busy,timeout=15000)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual(bridge.summary['empty'],0)
                self.assertFalse(action.property('enabled'))
                self.assertFalse(warnings,warnings)
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)
                if window:window.close()
                engine.deleteLater();APP.processEvents()

    def test_only_saved_empty_is_requeried_from_persisted_input_and_csv_keeps_existing_lines(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);database=seed(root)
            with closing(sqlite3.connect(database)) as db:
                unchanged=db.execute('SELECT * FROM jobs WHERE ordinal IN (2,3) ORDER BY ordinal').fetchall()
            (root/'base.xlsx').unlink()  # La reconsulta no depende del archivo ni del proveedor.
            bridge=BatchBridge(module_id='bls',storage_root=root,knowledge_root=root/'no_sources',offline_fixture=True)
            events=[];bridge.eventReceived.connect(events.append)
            try:
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                self.assertEqual(bridge.summary['empty'],1)
                selected=bridge.activeId
                self.assertTrue(bridge.command('retry_empty',{'recordId':selected}))
                wait_until(lambda:not bridge.busy,timeout=15000)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual((bridge.summary['succeeded'],bridge.summary['pending'],bridge.summary['empty'],bridge.summary['rows']),(2,1,0,2))
                self.assertEqual(bridge.activeId,selected)
                self.assertEqual(len(list(root.glob('data/jobs/bls/**/SQLite/bls.sqlite3'))),1)
                with closing(sqlite3.connect(database)) as db:
                    self.assertEqual(db.execute('SELECT * FROM jobs WHERE ordinal IN (2,3) ORDER BY ordinal').fetchall(),unchanged)
                    self.assertEqual(db.execute('SELECT state,attempts,result_count FROM jobs WHERE ordinal=1').fetchone(),('Guardado',2,1))
                    self.assertEqual(db.execute('SELECT count(*) FROM attempts').fetchone()[0],4)
                    self.assertEqual(db.execute('SELECT count(*) FROM workbench_empty_requeries').fetchone()[0],1)
                self.assertTrue(list((root/'data/backups/bls_empty').glob('*.sqlite3')))
                csvs=list((root/'resultados/BLS').rglob('*.csv'))
                self.assertEqual(len(csvs),1)
                text=csvs[0].read_text(encoding='utf-8-sig')
                self.assertIn('0000001',text);self.assertIn('0000002',text)
                self.assertNotIn('0000003',text)
                self.assertFalse(any(e.get('command')=='knowledge_build' for e in events))
                digest=hashlib.sha256(database.read_bytes()).hexdigest()
                self.assertTrue(bridge.command('retry_empty',{'recordId':selected}))
                wait_until(lambda:not bridge.busy)
                self.assertIn('No hay BLs',bridge.status)
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(),digest)
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)

    def test_changed_selection_and_external_lock_preserve_job_data(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);database=seed(root)
            bridge=BatchBridge(module_id='bls',storage_root=root,knowledge_root=root/'no_sources',offline_fixture=True)
            try:
                bridge.connectModule();wait_until(lambda:bridge.ready and not bridge.busy)
                digest=hashlib.sha256(database.read_bytes()).hexdigest()
                bridge.command('retry_empty',{'recordId':'otra-seleccion'})
                wait_until(lambda:not bridge.busy)
                self.assertIn('seleccionado cambió',bridge.error)
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(),digest)
                with RunLock(database):
                    bridge.command('retry_empty',{'recordId':bridge.activeId})
                    wait_until(lambda:not bridge.busy)
                    self.assertIn('Otra ejecución',bridge.error)
                self.assertEqual(hashlib.sha256(database.read_bytes()).hexdigest(),digest)
                self.assertFalse(list((root/'data/backups/bls_empty').glob('*.sqlite3')))
            finally:
                bridge.shutdown();wait_until(lambda:bridge.isClosed)


if __name__=='__main__':unittest.main()

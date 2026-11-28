"""Cambiar período lee SQLite existentes, sin preparar lotes ni consultar TICA."""
from contextlib import closing
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from threading import Event
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP, wait_until
from batch_bridge import BatchBridge
from details_bridge import DetailsBridge
from demo import DemoBackend
from preferences import Preferences
from chc_runtime.manifest_service import BatchService
from PySide6.QtCore import QObject, QUrl
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression

FLOWS=('tabla','conocimientos','duas','movimientos','contenedores')


def seed(root,flow):
    service=BatchService(root,flow,lambda *a,**k:None,Event())
    for year,month in ((2025,10),(2026,9),(2026,10)):
        identifier=f'{flow}-{year}-{month}'
        config={**service.index['config'],'year':year,'month':month,'name':identifier,
                'modes':['maritimo'] if flow=='contenedores' else ['maritimo','aereo']}
        record=dict(id=identifier,name=identifier,period=f'{year}-{month:02d}',
                    spec=dict(year=year,month=month,ids=[],limit=0),config=config,
                    summary={},databases=[],work=str(root/'data/jobs'/flow/identifier))
        for mode in config['modes']:
            path=Path(record['work'])/(mode+'.sqlite3');path.parent.mkdir(parents=True,exist_ok=True)
            with closing(sqlite3.connect(path)) as db:
                db.executescript('CREATE TABLE metadata(scope); CREATE TABLE rows(data); '
                    'CREATE TABLE jobs(id,ordinal,state,attempts,kept_count,error);')
                db.execute('INSERT INTO metadata VALUES (?)',(json.dumps(dict(mode=mode,year=year,month=month)),))
                db.executemany('INSERT INTO jobs VALUES (?,?,?,?,?,?)',
                    [('listado',1,'Guardado',2,month,''),('pendiente',2,'Descargando',1,0,'')])
                db.executemany('INSERT INTO rows VALUES (?)',[(f'000{i}',) for i in range(month)])
                db.commit()
            record['databases'].append(str(path))
        service.index['history'].append(record)
    service.index['active']=identifier
    service.index['config']=dict(config)
    service.inspect();service.save()
    (root/'conservar.CSV').write_bytes(b'ID\n00001\n')
    return service


def hashes(root):
    return {p:hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*')
            if p.suffix in ('.sqlite3','.CSV')}


class PeriodTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform=='win32' and os.environ.get('QT_QPA_PLATFORM')=='offscreen':
            fonts=Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'
            for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf','segoeuil.ttf'):
                QFontDatabase.addApplicationFont(str(fonts/name))
        APP.setFont(QFont('Segoe UI',10))

    def test_five_flows_month_year_empty_and_restore_are_readonly(self):
        with tempfile.TemporaryDirectory() as folder:
            for flow in FLOWS:
                with self.subTest(flow=flow):
                    root=Path(folder)/flow;service=seed(root,flow);before=hashes(root)
                    with patch.object(service,'prepare') as prepare, patch.object(service,'run') as run, patch.object(service,'export') as export:
                        for year,month in ((2026,9),(2026,11),(2026,10),(2025,10)):
                            snapshot=service.execute('select_period',dict(year=year,month=month))['snapshot']
                            self.assertEqual((snapshot['config']['year'],snapshot['config']['month']),(year,month))
                            if month==11:
                                self.assertFalse(snapshot['activeId']);self.assertFalse(snapshot['jobs'])
                                self.assertFalse(snapshot['modeSummaries']);self.assertFalse(snapshot['refreshSaved'])
                                self.assertFalse(snapshot['outputFolder'])
                                self.assertEqual(sum(snapshot['summary'].values()),0)
                                self.assertIn('No hay descargas',snapshot['message'])
                                self.assertEqual(snapshot['config']['start'],'')
                            else:
                                expected=f'{flow}-{year}-{month}'
                                self.assertEqual(snapshot['activeId'],expected)
                                self.assertEqual(snapshot['summary']['rows'],month*(1 if flow=='contenedores' else 2))
                                self.assertTrue(all(expected in job['database'] for job in snapshot['jobs']))
                                self.assertTrue(all(job['state']!='Descargando' for job in snapshot['jobs']))
                        prepare.assert_not_called();run.assert_not_called();export.assert_not_called()
                    self.assertEqual(hashes(root),before)
                    reopened=BatchService(root,flow,lambda *a,**k:None,Event())
                    self.assertEqual(reopened.index['active'],f'{flow}-2025-10')

    def test_multiple_records_prefer_monthly_and_keep_explicit_selection(self):
        with tempfile.TemporaryDirectory() as folder:
            service=seed(Path(folder),'movimientos')
            filtered=deepcopy(service.active());filtered['id']='filtered'
            filtered['spec']['ids']=['0001'];filtered['config']['manifestIds']='0001'
            filtered['summary']['succeeded']=999
            service.index['history'].append(filtered)
            service.execute('select_period',dict(year=2026,month=9))
            service.execute('select_period',dict(year=2026,month=10))
            self.assertEqual(service.index['active'],'movimientos-2026-10')
            service.execute('select',dict(id='filtered'))
            service.execute('select_period',dict(year=2026,month=10))
            self.assertEqual(service.index['active'],'filtered')
            service.execute('select_period',dict(year=2026,month=11))
            service.execute('select',dict(id='filtered'))
            self.assertEqual(service.message,'')

    def test_invalid_or_processing_selection_preserves_state(self):
        with tempfile.TemporaryDirectory() as folder:
            service=seed(Path(folder),'movimientos');before=deepcopy(service.index)
            for request in (dict(year=2026,month=13),dict(year=1999,month=10)):
                with self.assertRaises(ValueError):service.execute('select_period',request)
            service.processing=True
            with self.assertRaises(ValueError):service.execute('select_period',dict(year=2026,month=9))
            self.assertEqual(service.index,before)

    def test_qml_period_changes_real_worker_without_download_commands(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);manifest_root=root/'manifiestos'
            for flow in FLOWS:seed(manifest_root,flow)
            before=hashes(manifest_root)
            bridge=BatchBridge(storage_root=manifest_root,offline_fixture=True)
            bls=BatchBridge(module_id='bls',enabled=False,storage_root=root/'bls',offline_fixture=True)
            details=[DetailsBridge(enabled=False,module_id=m,storage_root=root/m)
                     for m in ('detalles','duas_transito','talon','xmovimientos')]
            here=Path(__file__).resolve().parents[1]
            backend=DemoBackend(here/'modules.json',*details,bridge,bls)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=details[0],transit=details[1],talon=details[2],movements=details[3],
                    manifests=bridge,bls=bls,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            backend.navigate('manifiestos');engine.load(QUrl.fromLocalFile(str(here/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings);window=engine.rootObjects()[0]
            events=[];bridge.eventReceived.connect(events.append)
            try:
                for flow in FLOWS:
                    page=window.findChild(QObject,'batchRealPage')
                    procedure=QQmlExpression(engine.rootContext(),page,'selectProcedure('+json.dumps(flow)+')')
                    procedure.evaluate();self.assertFalse(procedure.hasError())
                    APP.processEvents();wait_until(lambda:bridge.ready and not bridge.busy)
                    month=window.findChild(QObject,'manifestMonth');year=window.findChild(QObject,'manifestYear')
                    self.assertEqual(month.property('currentIndex'),9,(flow,bridge.config,warnings,events[-2:]))
                    # Cargar configuración no dispara otra selección de período.
                    expression=QQmlExpression(engine.rootContext(),page,'loadConfig()')
                    expression.evaluate();self.assertFalse(expression.hasError())
                    for target_year,target_month in ((2026,9),(2026,11),(2026,10),(2025,10)):
                        year.setProperty('value',target_year);month.setProperty('currentIndex',target_month-1)
                        self.assertFalse(window.findChild(QObject,'manifestStart').property('enabled'))
                        wait_until(lambda:not bridge.busy and (bridge.config['year'],bridge.config['month'])==(target_year,target_month))
                        self.assertFalse(bridge.error,bridge.error)
                        self.assertEqual(year.property('value'),target_year)
                        self.assertEqual(month.property('currentIndex'),target_month-1)
                        if target_month==11:
                            self.assertFalse(bridge.activeId);self.assertFalse(bridge.jobs)
                            self.assertEqual(bridge.summary['rows'],0)
                            self.assertFalse(window.findChild(QObject,'manifestRefreshSaved').property('enabled'))
                        else:
                            self.assertEqual(bridge.activeId,f'{flow}-{target_year}-{target_month}')
                            self.assertEqual(bridge.summary['rows'],target_month*(1 if flow=='contenedores' else 2))
                        capture=os.environ.get('CHC_PERIOD_CAPTURES')
                        if capture and flow=='movimientos' and target_year==2026 and target_month in (9,11):
                            destination=Path(capture);destination.mkdir(parents=True,exist_ok=True)
                            for width,height in ((1280,774),(1000,680),(1000,600)):
                                window.setWidth(width);window.setHeight(height);APP.processEvents()
                                self.assertTrue(window.grabWindow().save(str(destination/f'{width}x{height}-mes-{target_month}.png')))
                    # Dos cambios rápidos se resuelven juntos con el último período.
                    month.setProperty('currentIndex',8);month.setProperty('currentIndex',10)
                    wait_until(lambda:not bridge.busy and bridge.config['month']==11)
                    self.assertFalse(bridge.activeId)
                commands=[e['command'] for e in events if e.get('event')=='result']
                self.assertEqual(commands.count('select_period'),25)
                self.assertTrue(set(commands)<={'refresh','select_period'},commands)
                self.assertEqual(hashes(manifest_root),before)
                self.assertFalse(list(manifest_root.rglob('data/exports')))
                self.assertFalse(warnings,warnings)
                bridge.current().busy=True
                self.assertFalse(bridge.command('select_period',dict(year=2026,month=9)))
                bridge.current().busy=False
            finally:
                window.close();engine.deleteLater();APP.processEvents()
                bridge.shutdown();bls.shutdown();wait_until(lambda:bridge.isClosed and bls.isClosed)


if __name__=='__main__':unittest.main()

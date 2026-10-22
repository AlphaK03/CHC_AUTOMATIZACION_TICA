"""Auditoría visual aislada: páginas reales, ventanas y controles sin motores/red."""
import calendar
from datetime import date
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import APP
from test_active_jobs_qml import MemoryBatch
from details_bridge import DetailsBridge
from demo import DemoBackend
from preferences import Preferences
from sharepoint_bridge import SharePointBridge
from monthly_progress import MonthlyReader, month_days
from chc_runtime.manifest_service import BatchService, bls_job
from threading import Event
from PySide6.QtCore import QObject, Signal, QMetaObject, QUrl, Qt, QPointF
from PySide6.QtGui import QFontDatabase
from PySide6.QtQml import QQmlApplicationEngine, QQmlExpression
from PySide6.QtTest import QTest

HERE=Path(__file__).resolve().parents[1]


class StaticDetails(DetailsBridge):
    def connectModule(self):pass
    def _send(self,*a,**k):return False


class StaticCloud(SharePointBridge):
    def send(self,*a,**k):return False


class StaticMonthly(QObject):
    changed=Signal()
    busy=False
    message='Datos de prueba para comprobar la distribución.'
    def __init__(self):
        super().__init__()
        reader=MonthlyReader({},date(2026,11,1))
        for module in ('detalles','duas_transito','talon','xmovimientos','bls','manifiestos'):
            flows=('tabla','conocimientos','duas','movimientos','contenedores') if module=='manifiestos' else ('',)
            for flow in flows:reader.add('2026-10',module,flow,module,100,100,days=month_days('2026-10'))
        self.rows=reader.read()['rows']
    def refresh(self):pass
    def schedule(self):pass
    def setComplete(self,*a):pass


def walk(item):
    yield item
    for child in item.childItems():yield from walk(child)


class PlatformLayoutTests(unittest.TestCase):
    def test_pages_and_dialogs_fit_and_history_rows_are_reachable(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            if sys.platform=='win32':
                for name in ('segoeui.ttf','segoeuib.ttf','seguisb.ttf'):
                    QFontDatabase.addApplicationFont(str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/name))
            bridges=[]
            for module in ('detalles','duas_transito','talon','xmovimientos'):
                bridge=StaticDetails(module_id=module,storage_root=root/module)
                bridge._ready=True
                bridge._runtime['chromiumReady']=True
                bridge._snapshot['config']=dict(cant_hilos=4,timeout=30,max_retries=3,headless=True,
                    output_base_path=str(root/'resultados'),daily_mode=True,daily_start_date='2026-08-01')
                bridge._snapshot['summary'].update(total=2,succeeded=1,pending=1,attempts=2)
                bridge._snapshot['activeTable']=dict(id='test',name='Agosto 2026 · Datos de prueba')
                bridge._snapshot['tables']=[bridge._snapshot['activeTable']]
                bridge._view.update(total=2,rows=[dict(id=str(i),dua=f'001-2026-{i:06}',status='succeeded',
                    reason='Resultado guardado. Texto de prueba para inspeccionar el espacio.',attempts=1,error_kind='') for i in (1,2)])
                days=[]
                for day in calendar.Calendar().itermonthdates(2026,8):
                    days.append(dict(day=day.day if day.month==8 else 0,date=day.isoformat(),available=day.month==8,
                        state='pending',total=100,succeeded=80,empty=0,error=''))
                bridge._daily.update(month='2026-08',monthLabel='Agosto 2026',startDate='2026-08-01',days=days)
                bridge._detail=dict(dua='001-2026-000001',values=[dict(field='Campo '+str(i),value='000123 · Valor largo de prueba '*8) for i in range(30)],
                    resultRows=[],attemptHistory=[],sources=[],reason='Pendiente de verificación. '*12)
                bridges.append(bridge)
            manifests=MemoryBatch(storage_root=root/'manifiestos')
            bls=MemoryBatch(module_id='bls',storage_root=root/'bls')
            for flow in manifests.channels:
                service=BatchService(root/'manifiestos',flow,lambda *a,**k:None,Event())
                service.index['history']=[dict(id='test',name='octubre26',summary={},databases=[])]
                service.index['active']='test'
                service.index['config']['modes']=['maritimo','aereo']
                for mode,rows in (('maritimo',250),('aereo',1833)):
                    service.progress(dict(database=str(root/(mode+'.sqlite3')),mode=mode,
                        progress=dict(selected=1,saved=1,pending=0,active=0,excluded=0),
                        job=dict(id='listado',ordinal=1,state='Guardado',attempts=1,kept=rows)))
                manifests.channels[flow].snapshot=service.snapshot()
                manifests.channels[flow].ready=True
            manifests._flow='tabla'
            service=BatchService(root/'bls','bls',lambda *a,**k:None,Event())
            service.index['history']=[dict(id='test',name='BLs de prueba',summary=dict(total=2,succeeded=2,rows=2083),databases=[])]
            service.index['active']='test'
            service._jobs={i:bls_job(i,{'IDManifiesto':'1-0-20260001-P027-01/10/26','BL original':str(i)},'Guardado',1,100,'') for i in (1,2)}
            bls.current().snapshot=service.snapshot();bls.current().ready=True
            cloud=StaticCloud(root/'cloud')
            cloud._snapshot.update(connected=True,account='persona@chc.example',localRoot=str(root/'resultados'),
                destination=dict(folderId='test',path='Reportes de prueba'),months=[dict(period='2026-10',label='Octubre 2026')])
            monthly=StaticMonthly()
            backend=DemoBackend(HERE/'modules.json',*bridges,manifests,bls,monthly)
            engine=QQmlApplicationEngine();warnings=[]
            engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
            for name,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],
                    manifests=manifests,bls=bls,sharepoint=cloud,preferences=Preferences(root/'prefs',persist=False)).items():
                engine.rootContext().setContextProperty(name,value)
            engine.load(QUrl.fromLocalFile(str(HERE/'qml/Main.qml')))
            self.assertTrue(engine.rootObjects(),warnings)
            window=engine.rootObjects()[0]
            capture_root=Path(os.environ.get('CHC_LAYOUT_CAPTURES',root/'captures'))
            capture_root.mkdir(parents=True,exist_ok=True)
            report=[]
            def settle():QTest.qWait(35);APP.processEvents()
            def find(name):return window.findChild(QObject,name)
            def invoke(obj,method):self.assertTrue(QMetaObject.invokeMethod(obj,method,Qt.DirectConnection));settle()
            def close_popup(dialog):
                if dialog.objectName() in ('aboutDialog','roadmapDialog','detailsDatabaseDialog','detailsResultDialog'):
                    expression=QQmlExpression(engine.rootContext(),dialog,'footer.standardButton(2097152)')
                    button=expression.evaluate()[0]
                    self.assertFalse(expression.hasError(),expression.error().toString())
                    self.assertIsNotNone(button)
                    self.assertEqual(button.property('text'),'Cerrar')
                    invoke(button,'clicked')
                    self.assertFalse(dialog.property('visible'))
                else:invoke(dialog,'close')
            def scroll_end(view):
                flick=view.property('contentItem')
                self.assertIsNotNone(flick.property('contentY'))
                flick.setProperty('contentY',max(0,flick.property('contentHeight')-flick.property('height')))
                settle()
            def inspect(label,popup=None):
                settle();issues=[]
                if popup:
                    content=popup.property('contentItem')
                    origin=content.mapToScene(QPointF(0,0))
                    if origin.x() < -1 or origin.y() < -1 or origin.x()+content.width()>window.width()+1 or origin.y()+content.height()>window.height()+1:
                        issues.append('Contenido del diálogo fuera de la ventana')
                for item in walk(window.contentItem()):
                    if not item.isVisible() or item.width()<=0 or item.height()<=0:continue
                    cls=item.metaObject().className()
                    if not any(part in cls for part in ('Button','Field','Select','Choice','SpinBox','Toggle','NavItem')):continue
                    origin=item.mapToScene(QPointF(0,0))
                    if origin.x() < -2 or origin.x()+item.width()>window.width()+2:
                        issues.append(f'{item.objectName() or cls}: X={origin.x():.0f}, ancho={item.width():.0f}')
                stamp=f'{int(window.width())}x{int(window.height())}-{label}'
                image=window.grabWindow();image.save(str(capture_root/(stamp+'.png')))
                report.append(dict(view=stamp,issues=issues))
            try:
                for width,height in ((1280,774),(1000,680),(1000,600)):
                    window.setMinimumHeight(600);window.resize(width,height);settle()
                    backend.navigate('overview');settle();inspect('vista-general')
                    invoke(find('monthStartExpand'),'clicked');inspect('inicio-mensual')
                    invoke(find('monthStartExpand'),'clicked')
                    find('monthlyLog').setProperty('expandedMonth','2026-10')
                    scroll_end(find('dashboardPage'));inspect('vista-general-final')
                    for name in ('aboutDialog','roadmapDialog','manualMonthClose'):
                        dialog=find(name);invoke(dialog,'open');inspect(name,dialog);close_popup(dialog)
                    scroll_end(find('navigationScroll'))
                    nav=find('sharePointNavigation');nav_y=nav.mapToScene(QPointF(0,0)).y()
                    self.assertGreaterEqual(nav_y,0);self.assertLessEqual(nav_y+nav.height(),window.height())
                    inspect('navegacion-final')
                    find('navigationScroll').property('contentItem').setProperty('contentY',0)
                    for module in ('detalles','duas_transito','talon','xmovimientos'):
                        backend.navigate(module);settle()
                        page=find({'detalles':'detailsRealPage','duas_transito':'transitRealPage'}.get(module,module+'RealPage'))
                        inspect(module)
                        page.setProperty('tab',2);inspect(module+'-configuracion');page.setProperty('tab',0)
                        for name in ('detailsDatabaseDialog','detailsDailyCalendar','detailsResultDialog','detailsImportDialog','detailsImportConfirm','detailsRenameDialog','detailsDeleteDialog'):
                            dialog=find(name)
                            if name=='detailsDailyCalendar':
                                dialog.setProperty('selectedDay',dict(date='2026-08-01',state='pending',available=True,
                                    total=100,succeeded=80,error='Mensaje de validación largo para inspección. '*50))
                            invoke(dialog,'open');inspect(module+'-'+name,dialog)
                            if name=='detailsDailyCalendar':scroll_end(find('calendarScroll'));inspect(module+'-calendario-final',dialog)
                            close_popup(dialog)
                    for flow in ('tabla','conocimientos','duas','movimientos','contenedores'):
                        manifests._flow=flow;backend.navigate('manifiestos');manifests.changed.emit();settle()
                        page=find('batchRealPage');inspect(flow)
                        table=find('manifestJobs')
                        self.assertGreaterEqual(table.property('height'),86,'Ambas filas deben caber sin scroll interno')
                        scroll_end(page);inspect(flow+'-resultados')
                        rows=[item for item in walk(table) if item.objectName()=='batchJobRow']
                        self.assertEqual(len(rows),2)
                        for row in rows:
                            point=row.mapToItem(table,QPointF(0,0))
                            self.assertGreaterEqual(point.y(),-1)
                            self.assertLessEqual(point.y()+row.height(),table.property('height')+1)
                            scene=row.mapToScene(QPointF(0,0))
                            self.assertGreaterEqual(scene.y(),page.mapToScene(QPointF(0,0)).y()-1)
                            self.assertLessEqual(scene.y()+row.height(),window.height()-1)
                        page.setProperty('optionsVisible',True);inspect(flow+'-configuracion');page.setProperty('optionsVisible',False)
                    dialog=find('manifestBaseDialog');invoke(dialog,'open');inspect('crear-base',dialog);invoke(dialog,'close')
                    backend.navigate('bls');settle();inspect('bls')
                    page=find('batchRealPage');page.setProperty('optionsVisible',True);inspect('bls-configuracion');page.setProperty('optionsVisible',False)
                    dialog=find('blsKnowledgeDialog');invoke(dialog,'open');inspect('bls-conocimientos',dialog);invoke(dialog,'close')
                    dialog=find('sharePointDialog');invoke(dialog,'open');inspect('sharepoint',dialog)
                    dialog.setProperty('picking',True)
                    dialog.setProperty('sites',[dict(id='test',name='Sitio de prueba para reportes y documentos de trabajo '*4,url='https://example.invalid')])
                    inspect('sharepoint-selector',dialog)
                    cloud._browse=dict(driveId='test',folder=dict(id='root',name='Carpeta de reportes con un nombre muy largo '*4),
                        drives=[dict(id='test',name='Biblioteca de documentos de trabajo y archivos mensuales '*4)],
                        folders=[dict(id='one',name='Archivos de consulta mensual '*8)])
                    dialog.setProperty('selectedSite','Sitio de prueba con un nombre largo')
                    dialog.setProperty('driveId','test');cloud.changed.emit()
                    inspect('sharepoint-carpetas',dialog);invoke(dialog,'close')
                invoke(window,'toggleTheme')
                window.resize(1280,774)
                backend.navigate('overview');inspect('claro-vista-general')
                backend.navigate('manifiestos');settle();scroll_end(find('batchRealPage'));inspect('claro-manifiestos')
                backend.navigate('detalles');settle()
                dialog=find('detailsDatabaseDialog');invoke(dialog,'open');inspect('claro-base-datos',dialog);close_popup(dialog)
                dialog=find('sharePointDialog');invoke(dialog,'open');inspect('claro-sharepoint',dialog);invoke(dialog,'close')
                # También comprobar los espacios de demostración usados sin módulos habilitados.
                window.close();engine.deleteLater();APP.processEvents()
                disabled=DetailsBridge(enabled=False,storage_root=root/'disabled')
                demo_backend=DemoBackend(HERE/'modules.json',disabled)
                engine=QQmlApplicationEngine()
                engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
                engine.rootContext().setContextProperty('demo',demo_backend)
                engine.rootContext().setContextProperty('details',disabled)
                engine.rootContext().setContextProperty('preferences',Preferences(root/'demo-prefs',persist=False))
                engine.load(QUrl.fromLocalFile(str(HERE/'qml/Main.qml')))
                self.assertTrue(engine.rootObjects(),warnings)
                window=engine.rootObjects()[0]
                for width,height in ((1280,774),(1000,680),(1000,600)):
                    window.setMinimumHeight(600);window.resize(width,height)
                    for module in ('detalles','duas_transito','talon','xmovimientos','manifiestos','bls'):
                        demo_backend.navigate(module);inspect('demo-'+module)
                (capture_root/'audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
                self.assertFalse(warnings,warnings)
                self.assertFalse([r for r in report if r['issues']],json.dumps([r for r in report if r['issues']],ensure_ascii=False,indent=2))
            finally:
                window.close();engine.deleteLater();APP.processEvents()


if __name__=='__main__':unittest.main()

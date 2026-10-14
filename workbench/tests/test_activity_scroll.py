"""Mantener el mensaje visible ante progreso, inserciones, recorte y limpieza."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import RecordingBridge,APP
from test_details_bridge import wait_until,DetailsBridge
from demo import DemoBackend
from preferences import Preferences
from PySide6.QtCore import QObject,QUrl
from PySide6.QtQml import QQmlApplicationEngine,QQmlExpression

HERE=Path(__file__).resolve().parents[1]


class ActivityScrollTests(unittest.TestCase):
    def test_demo_panels_keep_reading_position_with_new_and_repeated_messages(self):
        bridge=DetailsBridge(enabled=False)
        backend=DemoBackend(HERE/'modules.json',bridge)
        backend._timer.stop()
        engine=QQmlApplicationEngine();warnings=[]
        engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
        context=engine.rootContext()
        prefs=Preferences(HERE/'unused-test-preferences.json',persist=False)
        for key,value in dict(demo=backend,details=bridge,preferences=prefs).items():context.setContextProperty(key,value)
        backend.navigate('bls')
        engine.load(QUrl.fromLocalFile(str(HERE/'qml/Main.qml')))
        self.assertTrue(engine.rootObjects(),warnings)
        window=engine.rootObjects()[0]
        try:
            for item in backend._modules:
                with self.subTest(module=item['id']):
                    backend.navigate(item['id'])
                    for index in range(30):backend._log(item,'Mismo mensaje, misma hora '+('extenso '*20 if index%3==0 else 'corto'))
                    APP.processEvents()
                    view=window.findChild(QObject,'activityView')
                    self.assertIsNotNone(view)
                    context.setContextProperty('testActivity',view)
                    def evaluate(code):
                        expr=QQmlExpression(context,view,code);value=expr.evaluate()
                        self.assertFalse(expr.hasError(),expr.error().toString())
                        return value[0] if isinstance(value,tuple) else value
                    wait_until(lambda:not view.property('restoreQueued'))
                    evaluate('testActivity.forceLayout();testActivity.positionViewAtIndex(8,0)')
                    APP.processEvents()
                    snapshot='JSON.stringify([testActivity.model.idAt(testActivity.indexAt(2,testActivity.contentY+1)),testActivity.contentY-testActivity.itemAtIndex(testActivity.indexAt(2,testActivity.contentY+1)).y])'
                    before=evaluate(snapshot)
                    backend.changed.emit();APP.processEvents()
                    self.assertEqual(evaluate(snapshot),before)
                    for _ in range(4):backend._log(item,'Mismo mensaje, misma hora')
                    wait_until(lambda:not view.property('restoreQueued'));APP.processEvents()
                    self.assertEqual(evaluate(snapshot),before)
                    self.assertEqual(view.property('count'),30)
            self.assertFalse(warnings,warnings)
        finally:
            window.setVisible(False)
            context.setContextProperty('testActivity',None)
            APP.processEvents()

    def test_all_real_dua_panels_preserve_viewport_and_follow_only_at_top(self):
        bridges=[RecordingBridge(module) for module in ('detalles','duas_transito','talon','xmovimientos')]
        backend=DemoBackend(HERE/'modules.json',*bridges)
        engine=QQmlApplicationEngine();warnings=[]
        engine.warnings.connect(lambda values:warnings.extend(w.toString() for w in values))
        context=engine.rootContext()
        prefs=Preferences(HERE/'unused-test-preferences.json',persist=False)
        for key,value in dict(demo=backend,details=bridges[0],transit=bridges[1],talon=bridges[2],movements=bridges[3],preferences=prefs).items():
            context.setContextProperty(key,value)
        backend.navigate('detalles')
        engine.load(QUrl.fromLocalFile(str(HERE/'qml/Main.qml')))
        self.assertTrue(engine.rootObjects(),warnings)
        window=engine.rootObjects()[0]
        try:
            for bridge in bridges:
                with self.subTest(module=bridge.moduleId):
                    bridge.activityModel.limit=80
                    for index in range(80):
                        bridge._receive(dict(event='log',time='12:00:00',level='INFO',message=f'Mensaje {index} '+('largo '*30 if index%3==0 else 'corto')))
                    backend.navigate(bridge.moduleId);APP.processEvents()
                    page=window.findChild(QObject,{'detalles':'detailsRealPage','duas_transito':'transitRealPage'}.get(bridge.moduleId,bridge.moduleId+'RealPage'))
                    view=page.findChild(QObject,'activityView');self.assertIsNotNone(view)
                    context.setContextProperty('testActivity',view)
                    def evaluate(code):
                        expression=QQmlExpression(context,view,code)
                        value=expression.evaluate()
                        self.assertFalse(expression.hasError(),expression.error().toString())
                        return value[0] if isinstance(value,tuple) else value
                    evaluate('testActivity.forceLayout(); testActivity.positionViewAtIndex(20,0); testActivity.contentY += 3')
                    APP.processEvents()
                    snapshot='''(() => {
                        testActivity.forceLayout();
                        let i=-1;
                        for(let y=1;y<30 && i<0;y++) i=testActivity.indexAt(2,testActivity.contentY+y);
                        let row=testActivity.itemAtIndex(i);
                        return JSON.stringify([testActivity.model.idAt(i),testActivity.contentY-row.y]);
                    })()'''
                    before=evaluate(snapshot)
                    bridge._receive({'event':'progress','summary':{'total':20,'succeeded':5,'pending':15}})
                    APP.processEvents()
                    self.assertEqual(evaluate(snapshot),before,'Un cambio de contadores no mueve la actividad.')
                    for index in range(5):
                        bridge._receive(dict(event='log',time='12:00:01',level='WARNING',message='Nuevo '+('texto '*40)))
                    wait_until(lambda:not view.property('restoreQueued'))
                    APP.processEvents()
                    self.assertEqual(evaluate(snapshot),before,'Insertar y recortar mensajes conserva la fila y el desplazamiento.')
                    evaluate('testActivity.followTop()');APP.processEvents()
                    bridge._receive(dict(event='log',time='12:00:02',level='SUCCESS',message='Último'))
                    wait_until(lambda:not view.property('restoreQueued'))
                    self.assertTrue(view.property('atYBeginning'))
                    self.assertIn(str(bridge.activityModel.rows[0]['activityId']),evaluate(snapshot))
                    evaluate('testActivity.positionViewAtEnd()');APP.processEvents()
                    for _ in range(4):bridge._receive(dict(event='log',time='12:00:02',level='INFO',message='Recorte del historial'))
                    wait_until(lambda:not view.property('restoreQueued'))
                    self.assertFalse(view.property('atYBeginning'),'Eliminar los mensajes más antiguos no devuelve al inicio.')
                    bridge.clearActivity();APP.processEvents()
                    self.assertEqual(view.property('count'),0)
                    bridge._receive(dict(event='log',time='12:00:03',level='INFO',message='Después de limpiar'))
                    wait_until(lambda:not view.property('restoreQueued'))
                    self.assertTrue(view.property('atYBeginning'))
            self.assertFalse(warnings,warnings)
        finally:
            # RecordingBridge no inicia workers; cerrar sin protocolo de motores.
            window.setVisible(False)
            context.setContextProperty('testActivity',None)
            APP.processEvents()


if __name__=='__main__':unittest.main()

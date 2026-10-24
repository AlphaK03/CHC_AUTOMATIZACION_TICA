"""La observación funciona con trabajo síncrono y no modifica resultados/plazos."""
import asyncio
import logging
import time
import unittest
from chc_runtime.activity import ActivityReporter, EventLog, observed, stage


class ReporterTests(unittest.TestCase):
    def setUp(self):
        self.events=[]
        self.reporter=ActivityReporter(lambda kind,**data:self.events.append(dict(event=kind,**data)),interval=.01,repeat=.02)

    def test_sync_export_reports_wait_without_claiming_success_and_stops(self):
        with self.reporter.session('Consultas'):
            with stage('Exportando CSV'):
                time.sleep(.08)
        states=[e for e in self.events if e['event']=='activity_state' and e['running']]
        self.assertTrue(any(any(row['label']=='Exportando CSV' for row in e['operations']) for e in states))
        self.assertTrue(any('Sigue en: Exportando CSV' in e.get('message','') for e in self.events))
        self.assertFalse(any(e.get('level')=='SUCCESS' for e in self.events))
        self.assertEqual(self.events[-1],dict(event='activity_state',running=False,operations=[]))
        count=len(self.events);time.sleep(.03)
        self.assertEqual(len(self.events),count)

    def test_decorator_preserves_result_and_exception_and_logging_levels(self):
        @observed('Validando')
        def function(value):
            if value<0:raise ValueError('identidad incorrecta')
            return value
        with self.reporter.session('Prueba'):
            self.assertEqual(function(42),42)
            with self.assertRaisesRegex(ValueError,'identidad incorrecta'):function(-1)
        handler=EventLog(lambda kind,**data:self.events.append(dict(event=kind,**data)))
        record=logging.LogRecord('test',logging.ERROR,'',1,'No se pudo leer %s',('TICA',),None)
        handler.emit(record)
        self.assertEqual(self.events[-1]['level'],'ERROR')
        self.assertEqual(self.events[-1]['message'],'No se pudo leer TICA')

    def test_concurrent_subjects_and_abandoned_tasks_disappear_with_supervisor(self):
        async def scenario():
            started=asyncio.Event();release=asyncio.Event()
            async def abandoned():
                with stage('Esperando HTTP','0001'):
                    started.set();await release.wait()
                    with stage('Respuesta tardía'):pass
            with self.reporter.session('Consulta'):
                with stage('Intento supervisado','0001'):
                    child=asyncio.create_task(abandoned())
                    await started.wait()
                    with stage('Otro hilo','0002'):
                        self.reporter.publish(self.reporter.generation)
                        rows=self.events[-1]['operations']
                        self.assertEqual({r['subject'] for r in rows},{'0001','0002'})
                self.reporter.publish(self.reporter.generation)
                self.assertFalse(any(r['subject']=='0001' for r in self.events[-1]['operations']))
                release.set();await child
            self.assertFalse(any(e.get('message')=='Respuesta tardía' for e in self.events))
        asyncio.run(scenario())


if __name__=='__main__':unittest.main()

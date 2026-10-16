"""Inicio mensual coordinado: respuestas exactas, dependencias y cancelación offline."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_qml_events import RecordingBridge,APP
from test_details_bridge import wait_until
from batch_bridge import BatchBridge
from month_launcher import MonthLauncher


class FakeDetails(RecordingBridge):
    def __init__(self,module='detalles'):
        super().__init__(module)
        self.requests=[]

    def _send(self,command,data=None):
        if self._busy and command!='stop':return False
        self._sequence+=1
        self.requests.append(dict(command=command,requestId=self._sequence,**(data or {})))
        self._busy=command!='stop'
        self.changed.emit()
        return True

    def acknowledge(self,error=False):
        request=self.requests[-1]
        if not error:self._snapshot['config'].update(request.get('config',{}))
        self._receive(dict(event='error' if error else 'result',command=request['command'],requestId=request['requestId'],message='Fallo de prueba'))
        self._receive(dict(event='idle',requestId=request['requestId'],readonly=False))


def fake_batch(module='manifiestos'):
    bridge=BatchBridge(module_id=module,enabled=True)
    bridge.sent=[]
    for flow,channel in bridge.channels.items():
        channel.ready=True
        channel.snapshot=copy.deepcopy(channel.snapshot)
        channel.snapshot['config']={'workers':2,'year':2026,'month':10,'modes':['aereo'],
            'start':'2026-10-01','end':'2026-10-05','manifestIds':'viejo','limit':2,'courier':'S'}
        def send(command,data=None,c=channel,f=flow):
            if c.busy and command!='stop':return False
            bridge.sent.append((f,command,copy.deepcopy(data or {})))
            c.busy=command!='stop';c.changed.emit()
            return True
        channel.send=send
    return bridge


def batch_event(bridge,flow,event):
    channel=bridge.channels[flow]
    if 'snapshot' in event:channel.snapshot=event['snapshot']
    if event['event']=='idle':channel.busy=False
    channel.changed.emit()
    bridge.receive(flow,event)


def completed(bridge,flow,pending=0):
    snapshot=copy.deepcopy(bridge.channels[flow].snapshot)
    snapshot['summary'].update(total=2,succeeded=2-pending,pending=pending,running=0)
    batch_event(bridge,flow,dict(event='result',command='run',snapshot=snapshot))
    batch_event(bridge,flow,dict(event='idle',command='run'))


class MonthLauncherTests(unittest.TestCase):
    def make(self,bridges):
        launcher=MonthLauncher(bridges)
        launcher.setPeriod(2026,9)
        self.addCleanup(launcher.timer.stop)
        return launcher

    def test_selection_workers_exact_month_and_matching_acknowledgement(self):
        details,transit=FakeDetails(),FakeDetails('duas_transito')
        launcher=self.make({'detalles':details,'duas_transito':transit})
        launcher.setSelected('detalles',True);launcher.setWorkers('detalles',7)
        launcher.start();launcher.start()
        self.assertEqual(len(details.requests),1);self.assertEqual(transit.requests,[])
        config=details.requests[0]['config']
        self.assertEqual((config['daily_start_date'],config['daily_end_date'],config['cant_hilos']),('2026-09-01','2026-09-30',7))
        details._receive(dict(event='result',command='configure',requestId=999))
        details._receive(dict(event='idle',requestId=999,readonly=True))
        APP.processEvents();self.assertEqual(len(details.requests),1)
        details.acknowledge();wait_until(lambda:len(details.requests)==2)
        self.assertEqual(details.requests[1]['command'],'daily_run')
        self.assertTrue(details.requests[1]['bounded'])
        launcher.cancel()

    def test_busy_bot_keeps_configuration_and_failure_does_not_start_it(self):
        details,transit=FakeDetails(),FakeDetails('duas_transito');transit._busy=True
        launcher=self.make({'detalles':details,'duas_transito':transit})
        launcher.setSelected('detalles',True);launcher.setSelected('duas_transito',True)
        launcher.start();details.acknowledge(error=True);APP.processEvents()
        self.assertEqual(transit.requests,[])
        self.assertEqual(launcher.tasks['duas_transito']['stage'],'skipped')
        self.assertEqual([r['command'] for r in details.requests],['configure'])
        self.assertFalse(launcher.active)

    def test_late_configuration_after_cancel_never_starts(self):
        details=FakeDetails();launcher=self.make({'detalles':details})
        launcher.setSelected('detalles',True);launcher.start()
        request=details.requests[-1]
        launcher.cancel()
        details._receive(dict(event='result',command='configure',requestId=request['requestId']))
        details._receive(dict(event='idle',requestId=request['requestId'],readonly=False))
        APP.processEvents()
        self.assertFalse(any(r['command']=='daily_run' for r in details.requests))

    def test_bls_waits_for_exact_completed_knowledge_and_uses_selected_workers(self):
        manifests,bls=fake_batch(),fake_batch('bls')
        launcher=self.make({'manifiestos':manifests,'bls':bls})
        launcher.setSelected('conocimientos',True);launcher.setSelected('bls',True)
        launcher.setMode('aereo',True);launcher.setWorkers('bls',6)
        launcher.start()
        self.assertEqual(launcher.tasks['bls']['stage'],'dependency');self.assertEqual(bls.sent,[])
        config=manifests.sent[0][2]['config']
        self.assertEqual((config['year'],config['month'],config['start'],config['end']), (2026,9,'2026-09-01','2026-09-30'))
        self.assertEqual((config['limit'],config['manifestIds'],config['courier']),(0,'','todos'))
        completed(manifests,'conocimientos')
        self.assertEqual(bls.sent[-1][:2],('bls_source','knowledge_catalog'))
        catalog={'periods':[{'key':'2026-09|maritimo','fullMonth':True},{'key':'2026-09|aereo','fullMonth':True}]}
        snapshot=copy.deepcopy(bls.channels['bls_source'].snapshot);snapshot['knowledgeCatalog']=catalog
        batch_event(bls,'bls_source',dict(event='result',command='knowledge_catalog',snapshot=snapshot))
        self.assertFalse(any(command=='knowledge_build' for _,command,_ in bls.sent))
        batch_event(bls,'bls_source',dict(event='idle',command='knowledge_catalog'))
        wait_until(lambda:any(command=='knowledge_build' for _,command,_ in bls.sent))
        self.assertEqual(bls.sent[-1][2]['periods'],['2026-09|maritimo','2026-09|aereo'])
        self.assertEqual(bls._knowledge_request['workers'],6)
        launcher.cancel();self.assertIsNone(bls._knowledge_request)
        batch_event(bls,'bls_source',dict(event='result',command='knowledge_build',knowledgeBase={'output':'tardio.sqlite3','empty':False}))
        self.assertFalse(any(flow=='bls' and command=='run' for flow,command,_ in bls.sent))

    def test_pending_knowledge_and_partial_catalog_never_launch_bls(self):
        manifests,bls=fake_batch(),fake_batch('bls')
        launcher=self.make({'manifiestos':manifests,'bls':bls})
        launcher.setSelected('conocimientos',True);launcher.setSelected('bls',True)
        launcher.start();completed(manifests,'conocimientos',pending=1)
        self.assertEqual(launcher.tasks['bls']['stage'],'blocked');self.assertEqual(bls.sent,[])
        launcher.setSelected('conocimientos',False);launcher.start()
        snapshot=copy.deepcopy(bls.channels['bls_source'].snapshot)
        snapshot['knowledgeCatalog']={'periods':[{'key':'2026-09|maritimo','fullMonth':False}]}
        batch_event(bls,'bls_source',dict(event='result',command='knowledge_catalog',snapshot=snapshot))
        batch_event(bls,'bls_source',dict(event='idle',command='knowledge_catalog'))
        wait_until(lambda:launcher.tasks['bls']['stage']=='blocked')
        self.assertEqual(launcher.tasks['bls']['stage'],'blocked')
        self.assertFalse(any(command=='knowledge_build' for _,command,_ in bls.sent))

    def test_future_month_and_worker_limits_validated_without_commands(self):
        details=FakeDetails();launcher=self.make({'detalles':details})
        launcher.setSelected('detalles',True);launcher.setWorkers('detalles',999)
        self.assertEqual(next(i['workers'] for i in launcher.items if i['id']=='detalles'),20)
        launcher.setPeriod(2100,12);launcher.start()
        self.assertEqual(details.requests,[]);self.assertFalse(launcher.active)

    def test_existing_matching_knowledge_is_observed_and_never_stopped_by_bulk_cancel(self):
        manifests,bls=fake_batch(),fake_batch('bls')
        channel=manifests.channels['conocimientos'];channel.busy=True
        channel.snapshot['config'].update(year=2026,month=9,modes=['maritimo'],start='',end='',manifestIds='',limit=0,courier='todos')
        launcher=self.make({'manifiestos':manifests,'bls':bls})
        launcher.setSelected('conocimientos',True);launcher.setSelected('bls',True);launcher.start()
        self.assertEqual(launcher.tasks['bls']['stage'],'dependency')
        self.assertEqual(manifests.sent,[])
        launcher.cancel()
        self.assertEqual(manifests.sent,[])
        completed(manifests,'conocimientos');APP.processEvents()
        self.assertEqual(bls.sent,[])

    def test_stop_from_bot_panel_cancels_pending_configuration(self):
        details=FakeDetails();launcher=self.make({'detalles':details})
        launcher.setSelected('detalles',True);launcher.start()
        details._receive(dict(event='stopping'))
        details.acknowledge();APP.processEvents()
        self.assertFalse(any(r['command']=='daily_run' for r in details.requests))

    def test_changed_configuration_before_dispatch_never_runs_wrong_month(self):
        details=FakeDetails();launcher=self.make({'detalles':details})
        launcher.setSelected('detalles',True);launcher.start();details.acknowledge()
        details._snapshot['config']['daily_start_date']='2026-08-01'
        APP.processEvents()
        self.assertFalse(any(r['command']=='daily_run' for r in details.requests))
        self.assertEqual(launcher.tasks['detalles']['stage'],'error')

    def test_closing_between_catalog_and_dispatch_does_not_restart_provider(self):
        bls=fake_batch('bls');launcher=self.make({'bls':bls})
        launcher.setSelected('bls',True);launcher.start()
        snapshot=copy.deepcopy(bls.channels['bls_source'].snapshot)
        snapshot['knowledgeCatalog']={'periods':[{'key':'2026-09|maritimo','fullMonth':True}]}
        batch_event(bls,'bls_source',dict(event='result',command='knowledge_catalog',snapshot=snapshot))
        batch_event(bls,'bls_source',dict(event='idle',command='knowledge_catalog'))
        bls._closing=True;APP.processEvents()
        self.assertFalse(any(command=='knowledge_build' for _,command,_ in bls.sent))
        self.assertEqual(launcher.tasks['bls']['stage'],'stopped')

    def test_terrestrial_only_does_not_queue_unsupported_bls(self):
        manifests,bls=fake_batch(),fake_batch('bls')
        launcher=self.make({'manifiestos':manifests,'bls':bls})
        launcher.setSelected('conocimientos',True);launcher.setSelected('bls',True)
        launcher.setMode('maritimo',False);launcher.setMode('terrestre',True);launcher.start()
        self.assertEqual(launcher.tasks['bls']['stage'],'blocked')
        self.assertEqual(bls.sent,[])
        self.assertEqual(manifests.sent[0][2]['config']['modes'],['terrestre'])
        launcher.cancel()


if __name__=='__main__':unittest.main()

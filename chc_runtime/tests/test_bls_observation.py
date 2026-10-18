"""Estados reales del adaptador: modalidades, páginas repetidas y recuperación."""
from pathlib import Path
import sys
import tempfile
from threading import Event
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'bots/bls/src'))
import pandas as pd
from config_manager import DEFAULTS
from chc_runtime.bls_session import WorkbenchBLSProcessor


class BlsObservationTests(unittest.IsolatedAsyncioTestCase):
    async def test_live_saved_empty_and_failed_modes_then_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            events=[];fail=True;queried=[]
            data=pd.DataFrame([{'IDManifiesto':f'{mode}-1-000123-P001-13/10/26',
                'Secuencia Tica':str(i),'BL original':f'{i:09d}',
                'Fecha Manifiesto':'13/10/2026','Mes':'2026-10'} for i,mode in ((1,'1'),(2,'1'),(3,'4'))])
            class Session:
                async def query(self,record):
                    queried.append(record['BL original'])
                    if record['BL original']=='000000003' and fail:
                        raise RuntimeError('Fallo temporal de prueba')
                    return dict(status='success',columns=['dato','manifiesto','bls'],
                        rows=[] if record['BL original']=='000000002' else [['fila',record['IDManifiesto'],record['BL original']]])
                async def close(self):pass
            config={**DEFAULTS,'output_base_path':folder,'cant_hilos':1,'max_retries':1,'event_callback':events.append}
            await WorkbenchBLSProcessor(config,Event()).run_async(data,session_factory=lambda _:Session())
            sea,air=events[-1]['modeSummaries']
            self.assertEqual((sea['total'],sea['succeeded'],sea['empty'],sea['rows']),(2,2,1,1))
            self.assertEqual((air['total'],air['pending'],air['running']),(1,1,0))
            downloading=[e for e in events if e.get('job',{}).get('state')=='Descargando']
            self.assertEqual(len(downloading),3)
            self.assertEqual(downloading[-1]['modeSummaries'][1]['running'],1)
            self.assertEqual(downloading[-1]['modeSummaries'][0]['succeeded'],2)
            fail=False;queried.clear();events.clear()
            await WorkbenchBLSProcessor(config,Event()).run_async(data,session_factory=lambda _:Session())
            self.assertEqual(queried,['000000003'])
            self.assertEqual([s['succeeded'] for s in events[-1]['modeSummaries']],[2,1])

    def test_page_events_do_not_confirm_or_double_count_bl(self):
        from chc_runtime.bls_observation import BlsModeProgress
        progress=BlsModeProgress()
        event=dict(ordinal=1,manifest='4-1-000123-P001-13/10/26',state='Descargando',result_count=0)
        for page in range(1,5):progress.update(dict(event,page=page,collectedRows=page*50))
        air=progress.summaries()[0]
        self.assertEqual((air['total'],air['running'],air['succeeded'],air['rows']),(1,1,0,0))
        progress.update(dict(event,state='Guardado',result_count=200))
        progress.update(dict(event,state='Guardado',result_count=200))
        air=progress.summaries()[0]
        self.assertEqual((air['total'],air['running'],air['succeeded'],air['rows']),(1,0,1,200))


if __name__=='__main__':unittest.main()

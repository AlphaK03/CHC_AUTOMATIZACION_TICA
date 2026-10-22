"""Entrar a BLs no relee bases; una actualización explícita sí ve nuevos datos."""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_details_bridge import wait_until
from test_bls_knowledge import sources
from batch_bridge import BatchBridge


class LoadingConnectionTests(unittest.TestCase):
    def test_navigation_reuses_loaded_data_and_explicit_refresh_reads_new_sources(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            bridge=BatchBridge(module_id='bls',storage_root=root/'bls',
                               knowledge_root=root/'manifiestos',offline_fixture=True)
            source=bridge.channels['bls_source']
            events=[]
            bridge.eventReceived.connect(events.append)
            try:
                bridge.connectModule()
                bridge.connectModule()  # Entrar durante el arranque no encola otra lectura.
                wait_until(lambda:bridge.ready and not bridge.busy)
                self.assertTrue(bridge._knowledge_loaded)
                initial=deepcopy(bridge.current().snapshot)
                catalog=deepcopy(bridge.knowledgeCatalog)
                self.assertEqual(catalog['periods'],[])
                commands=[e for e in events if e.get('event')=='result' and e.get('command')=='knowledge_catalog']
                self.assertEqual(len(commands),1)
                with patch.object(source,'send',wraps=source.send) as send_source, \
                     patch.object(bridge.current(),'send',wraps=bridge.current().send) as send_bot:
                    for _ in range(4):bridge.connectModule()
                    send_source.assert_not_called()
                    send_bot.assert_not_called()
                self.assertEqual(bridge.current().snapshot,initial)
                self.assertEqual(bridge.knowledgeCatalog,catalog)
                sources(root/'manifiestos')
                bridge.refreshModule()  # Conserva la acción Más > Reconectar.
                wait_until(lambda:not bridge.busy)
                self.assertFalse(bridge.error,bridge.error)
                self.assertEqual(bridge.current().snapshot,initial)
                self.assertEqual({p['key'] for p in bridge.knowledgeCatalog['periods']},
                    {'2026-09|maritimo','2026-09|aereo','2026-08|aereo','2026-03|maritimo'})
                refreshed=deepcopy(bridge.knowledgeCatalog)
                # Una actualización de Conocimientos durante una lectura no se pierde.
                bridge.refreshKnowledge()
                bridge.refreshKnowledge()
                wait_until(lambda:not bridge.busy and not bridge._refresh_knowledge)
                self.assertEqual(bridge.knowledgeCatalog,refreshed)
            finally:
                bridge.shutdown()
                wait_until(lambda:bridge.isClosed)


if __name__=='__main__':unittest.main()

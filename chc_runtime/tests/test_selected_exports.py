"""El worker exporta solo IDs pedidos sin cambiar la selección ni consultar."""
from threading import Event
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from chc_runtime.worker import DetailsService
from chc_runtime.manifest_service import BatchService


class SelectedExportTests(unittest.TestCase):
    def test_dua_and_manifest_only_export_selected_ids_without_changing_active_or_configuration(self):
        records=[dict(id=str(i),name='Lote '+str(i)) for i in (1,2,3)]
        for execute,kind in ((DetailsService.execute,'dua'),(BatchService.execute,'manifest')):
            with self.subTest(kind=kind):
                export=Mock()
                service=SimpleNamespace(catalog=SimpleNamespace(list_tables=lambda:records),stop_event=Event(),stop=Event(),
                    index={'history':records,'active':'3','config':{'month':9}},active_id='3',export_record=export,export=export,snapshot=lambda:{})
                result=execute(service,'export_selected',{'recordIds':['2','1','1'],'exportToken':'token'})
                self.assertEqual([call.args[0]['id'] for call in export.call_args_list],['1','2'])
                self.assertEqual(result['exportReport'],{'token':'token','exported':2,'errors':[]})
                self.assertEqual((service.index['active'],service.active_id,service.index['config']),('3','3',{'month':9}))
                export.reset_mock()
                with self.assertRaises(ValueError):execute(service,'export_selected',{'recordIds':['unknown']})
                export.assert_not_called()


if __name__=='__main__':unittest.main()

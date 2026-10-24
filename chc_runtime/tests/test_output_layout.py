import csv
from pathlib import Path
import tempfile
import unittest

from chc_runtime import output_layout as layout


class OutputLayoutTests(unittest.TestCase):
    def test_period_and_all_bot_names(self):
        self.assertEqual(layout.period('Octubre 2026'),'2026-10')
        self.assertEqual(layout.period('enero27'),'2027-01')
        self.assertEqual(layout.period('daily://2026-09'),'2026-09')
        self.assertEqual(layout.period('muestra sin fecha'),'')
        for target in [*layout.BOTS,*('manifiestos:'+f for f in layout.FLOWS)]:
            spec=layout.specification(target,'2026-10')
            self.assertEqual(spec['filename'],spec['filename'].upper())
            self.assertEqual(spec['relativeFolders'][-1],'OCTUBRE_2026')
        self.assertEqual(layout.specification('manifiestos:conocimientos','2026-10','aereo')['filename'],
                         'MANIFIESTOS_CONOCIMIENTOS_AEREO_OCTUBRE_2026.CSV')

    def test_common_root_and_owner_protection_preserve_bytes(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);settings=root/'exports.json';source=root/'original.csv'
            source.write_bytes(b'codigo,valor\r\n000023,125.50\r\n')
            layout.set_local_root(root/'RESULTADOS',settings=settings)
            self.assertEqual(layout.local_root(settings=settings),root/'RESULTADOS')
            spec=layout.specification('talon','2026-10')
            result=layout.publish(source,layout.local_root(settings=settings),spec,'talon:uno',layout.registry_path(settings=settings))
            destination=Path(result['path'])
            self.assertEqual(destination.read_bytes(),source.read_bytes())
            with self.assertRaises(ValueError):
                layout.publish(source,root/'RESULTADOS',spec,'talon:otro',layout.registry_path(settings=settings))
            self.assertEqual(destination.read_bytes(),source.read_bytes())

    def test_bls_split_preserves_rows_columns_and_actual_period(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'bls.csv'
            rows=[['codigo','manifiesto','bls'],['0001','1-001-10/10/26','000089'],
                  ['0002','4-002-10/10/26','000090'],['0003','1-003-10/09/26','000091']]
            with source.open('w',encoding='utf-8-sig',newline='') as stream:csv.writer(stream).writerows(rows)
            outputs=layout.bls_exports(source,{'name':'octubre26','config':{'inputMode':'knowledge'}})
            self.assertEqual(len(outputs),3)
            recovered=[]
            for path,spec in outputs:
                with path.open(encoding='utf-8-sig',newline='') as stream:data=list(csv.reader(stream))
                self.assertEqual(data[0],rows[0]);recovered.extend(data[1:])
                self.assertIn(spec['mode'],('MARITIMO','AEREO'))
                path.unlink()
            self.assertCountEqual(recovered,rows[1:])
            self.assertEqual({spec['period'] for _,spec in outputs},{'2026-09','2026-10'})

    def test_partial_manifest_does_not_collide_with_complete_month(self):
        record={'spec':{'year':2026,'month':10,'start':'2026-10-03','end':'2026-10-04'}}
        partial=layout.manifest_spec('tabla',record,'maritimo')
        complete=layout.manifest_spec('tabla',{'spec':{'year':2026,'month':10}},'maritimo')
        self.assertNotEqual(partial['filename'],complete['filename'])
        self.assertIn('DEL_2026_10_03_AL_2026_10_04',partial['filename'])


if __name__=='__main__':unittest.main()

"""La bitácora no confunde una selección terminada con un mes completo."""
from contextlib import contextmanager
from datetime import date
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from monthly_progress import MonthlyReader,month_days


@contextmanager
def write(path):
    db=sqlite3.connect(path)
    try:
        with db:yield db
    finally:db.close()


class MonthlyTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.today=date(2026,10,13)

    def tearDown(self):self.temp.cleanup()

    def reader(self):return MonthlyReader({'detalles':self.root},self.today)

    def dua_table(self,source='daily://2026-09',done=True):
        folder=self.root/'data/queues';folder.mkdir(parents=True)
        with write(folder/'catalog.sqlite3') as db:
            db.execute('CREATE TABLE saved_tables(id,name,filename,source_path,source_sheet,deleted)')
            db.execute('INSERT INTO saved_tables VALUES (?,?,?,?,?,0)',('id','septiembre26','month.sqlite3',source,'BLS'))
        with write(folder/'month.sqlite3') as db:
            db.execute('CREATE TABLE jobs(dua,status,result)')
            for day in range(1,31):
                db.execute('INSERT INTO jobs VALUES (?,?,?)',(str(day),'succeeded' if done or day!=30 else 'retry','[]' if done or day!=30 else None))
        return folder/'month.sqlite3'

    def ledger(self,count=30):
        folder=self.root/'data/daily';folder.mkdir(parents=True)
        with write(folder/'calendar.sqlite3') as db:
            db.execute('CREATE TABLE days(day,state,base_ready,total,table_id)')
            db.execute('CREATE TABLE daily_duas(day,dua)')
            for number in range(1,count+1):
                day=f'2026-09-{number:02d}'
                db.execute('INSERT INTO days VALUES (?,?,?,?,?)',(day,'completed',1,1,'id'))
                db.execute('INSERT INTO daily_duas VALUES (?,?)',(day,str(number)))

    def cell(self,result,module='detalles'):return next(c for c in result['rows'][0]['cells'] if c['module']==module)

    def test_full_calendar_and_results_complete_month_without_writing(self):
        self.dua_table();self.ledger()
        files=list(self.root.rglob('*.sqlite3'))
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
        result=self.reader().read()
        self.assertEqual(self.cell(result)['status'],'completed')
        self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in files},hashes)

    def test_partial_calendar_or_stale_completed_day_is_never_month_complete(self):
        self.dua_table(done=False);self.ledger()
        self.assertEqual(self.cell(self.reader().read())['status'],'partial')
        with write(self.root/'data/queues/month.sqlite3') as db:
            db.execute("UPDATE jobs SET status='succeeded',result='[]'")
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("DELETE FROM days WHERE day='2026-09-30'")
        self.assertEqual(self.cell(self.reader().read())['status'],'partial')

    def test_monthly_name_and_finished_import_do_not_prove_coverage(self):
        self.dua_table(source='base.xlsx')
        self.assertEqual(self.cell(self.reader().read())['status'],'ready')

    def test_omitted_day_with_unsaved_data_never_marks_month_complete(self):
        self.dua_table(done=False);self.ledger()
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("UPDATE days SET state='omitted' WHERE day='2026-09-30'")
        self.assertNotEqual(self.cell(self.reader().read())['status'],'completed')

    def test_month_with_failed_bases_and_no_table_is_still_visible_as_pending(self):
        self.ledger(count=2)
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("UPDATE days SET state='omitted',base_ready=0,table_id=''")
        result=self.reader().read()
        self.assertEqual(result['rows'][0]['period'],'2026-09')
        self.assertEqual(self.cell(result)['status'],'pending')
        self.assertIn('2 días',self.cell(result)['detail'])

    def test_completed_days_do_not_hide_added_pending_jobs(self):
        path=self.dua_table();self.ledger()
        with write(path) as db:db.execute("INSERT INTO jobs VALUES ('extra','pending',NULL)")
        self.assertNotEqual(self.cell(self.reader().read())['status'],'completed')

    def test_xmovimientos_empty_requires_observation_and_counts_as_consulted_not_saved(self):
        path=self.dua_table();self.ledger()
        with write(path) as db:
            db.execute('ALTER TABLE jobs ADD COLUMN id TEXT')
            db.execute('UPDATE jobs SET id=dua')
            db.execute('CREATE TABLE empty_observations(job_id,checked_at,evidence)')
            db.execute("UPDATE jobs SET status='empty',result=NULL WHERE dua='30'")
            db.execute("INSERT INTO empty_observations VALUES ('30','2026-09-30','evidence.html')")
        reader=MonthlyReader({'xmovimientos':self.root},self.today)
        result=reader.read()
        self.assertEqual(self.cell(result,'xmovimientos')['status'],'completed')
        self.assertIn('29 guardados',self.cell(result,'xmovimientos')['detail'])
        self.assertIn('1 vacíos',self.cell(result,'xmovimientos')['detail'])
        with write(path) as db:db.execute('DELETE FROM empty_observations')
        result=MonthlyReader({'xmovimientos':self.root},self.today).read()
        self.assertNotEqual(self.cell(result,'xmovimientos')['status'],'completed')

    def manifest(self,name,start='',end='',mode='maritimo',pending=False,limit=0,month=9,flow='conocimientos'):
        folder=self.root/'data/jobs'/flow/name;folder.mkdir(parents=True)
        path=folder/'progress.sqlite3'
        with write(path) as db:
            db.executescript('CREATE TABLE metadata(scope);CREATE TABLE jobs(id,state);CREATE TABLE manifests(id);'
                'CREATE TABLE selection(id);CREATE TABLE partial_pages(manifest);CREATE TABLE runs(state,finished);')
            db.execute('INSERT INTO metadata VALUES (?)',(json.dumps(dict(year=2026,month=month,mode=mode,desde=start,hasta=end,limit=limit)),))
            db.execute('INSERT INTO selection VALUES (1)')
            db.execute('INSERT INTO jobs VALUES (?,?)',('1','Pendiente' if pending else 'Guardado'))
            if not pending:db.execute("INSERT INTO manifests VALUES ('1')")
            db.execute("INSERT INTO runs VALUES ('Finalizada','date')")
        return path

    def test_manifest_counts_override_history_and_partial_filters(self):
        path=self.manifest('full',pending=True)
        reader=MonthlyReader({'manifiestos':self.root},self.today)
        reader.read()
        self.assertEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'pending')
        with write(path) as db:
            db.execute("UPDATE jobs SET state='Guardado'");db.execute("INSERT INTO manifests VALUES ('1')")
            db.execute("INSERT INTO partial_pages VALUES ('1')")
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        self.assertNotEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'completed')

    def test_disjoint_ranges_merge_only_within_the_same_mode(self):
        self.manifest('first','2026-09-01','2026-09-15')
        path=self.manifest('last','2026-09-16','2026-09-30',mode='aereo')
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        self.assertEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'ready')
        with write(path) as db:
            scope=json.loads(db.execute('SELECT scope FROM metadata').fetchone()[0]);scope['mode']='maritimo'
            db.execute('UPDATE metadata SET scope=?',(json.dumps(scope),))
        reader=MonthlyReader({'manifiestos':self.root},self.today);result=reader.read()
        self.assertEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'completed')
        self.assertEqual(self.cell(result,'manifiestos')['label'],'1/5 completos')

    def test_completed_sea_does_not_hide_pending_air(self):
        self.manifest('sea')
        self.manifest('air',mode='aereo',pending=True)
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        self.assertNotEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'completed')
        self.assertIn('maritimo',reader.cell('2026-09','manifiestos','conocimientos')['detail'])

    def test_current_month_never_completed_and_missing_database_not_success(self):
        reader=self.reader()
        reader.add('2026-10','detalles','','octubre26',1,1,days=month_days('2026-10'))
        self.assertNotEqual(reader.cell('2026-10','detalles')['status'],'completed')
        path=self.dua_table();path.unlink()
        result=self.reader().read()
        self.assertEqual(self.cell(result)['status'],'unknown')
        self.assertEqual(result['errors'],1)

    def test_bls_multi_month_is_grouped_from_jobs_not_current_configuration(self):
        index=self.root/'data/workbench/bls/session.json';index.parent.mkdir(parents=True)
        work=self.root/'data/jobs/bls/batch';folder=work/'BLS/signature/SQLite';folder.mkdir(parents=True)
        source=self.root/'base.sqlite3'
        source.with_suffix('.json').write_text(json.dumps({'coverage':[{'key':'2026-09|maritimo','fullMonth':True},{'key':'2026-08|maritimo','fullMonth':True}]}))
        index.write_text(json.dumps({'history':[{'name':'varios meses','spec':{'input':str(source)},'work':str(work),'config':{'month':10}}]}))
        with write(folder/'bls.sqlite3') as db:
            db.executescript('CREATE TABLE jobs(id,payload,state,result_count);CREATE TABLE results(job);')
            for key,state in [('2026-09','Pendiente'),('2026-08','Guardado')]:
                db.execute('INSERT INTO jobs VALUES (?,?,?,?)',(key,json.dumps({'Mes':key}),state,1 if state=='Guardado' else 0))
                if state=='Guardado':db.execute('INSERT INTO results VALUES (?)',(key,))
        result=MonthlyReader({'bls':self.root},self.today).read()
        self.assertEqual([r['period'] for r in result['rows']],['2026-09','2026-08'])
        self.assertEqual(self.cell(result,'bls')['status'],'pending')
        self.assertEqual(next(c for c in result['rows'][1]['cells'] if c['module']=='bls')['status'],'completed')
        with write(folder/'bls.sqlite3') as db:
            db.execute('ALTER TABLE jobs ADD COLUMN attempts INTEGER DEFAULT 3')
            db.execute('CREATE TABLE runs(state,finished)')
            db.execute("INSERT INTO runs VALUES ('Pendiente','date')")
        self.assertEqual(self.cell(MonthlyReader({'bls':self.root},self.today).read(),'bls')['status'],'completed')
        with write(folder/'bls.sqlite3') as db:db.execute("UPDATE runs SET state='Detenido'")
        self.assertNotEqual(self.cell(MonthlyReader({'bls':self.root},self.today).read(),'bls')['status'],'completed')

    def test_omitted_duas_close_other_bots_without_changing_pending_rows(self):
        path=self.dua_table(done=False);self.ledger()
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("UPDATE days SET state='omitted' WHERE day='2026-09-30'")
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        for module in ('duas_transito','talon','xmovimientos'):
            cell=self.cell(MonthlyReader({module:self.root},self.today).read(),module)
            self.assertEqual(cell['status'],'completed')
            self.assertIn('1 omitidos',cell['detail'])
        self.assertNotEqual(self.cell(self.reader().read())['status'],'completed')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)

    def test_current_month_is_up_to_date_only_with_all_available_days(self):
        self.dua_table(source='daily://2026-10');self.ledger(count=12)
        with write(self.root/'data/queues/catalog.sqlite3') as db:db.execute("UPDATE saved_tables SET name='octubre26'")
        with write(self.root/'data/daily/calendar.sqlite3') as db:
            db.execute("UPDATE days SET day=replace(day,'2026-09','2026-10')")
            db.execute("UPDATE daily_duas SET day=replace(day,'2026-09','2026-10')")
        cell=self.cell(self.reader().read())
        self.assertEqual(cell['status'],'up_to_date')
        self.assertIn('2026-10-12',cell['detail'])
        with write(self.root/'data/daily/calendar.sqlite3') as db:db.execute("DELETE FROM days WHERE day='2026-10-12'")
        self.assertNotEqual(self.cell(self.reader().read())['status'],'up_to_date')

    def test_manual_close_persists_is_reversible_and_expires_when_data_changes(self):
        path=self.dua_table(done=False);self.ledger()
        reader=MonthlyReader({'talon':self.root},self.today);reader.read()
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        reader.mark_complete('2026-09','talon',True)
        reader=MonthlyReader({'talon':self.root},self.today)
        cell=self.cell(reader.read(),'talon')
        self.assertEqual(cell['label'],'Completado manual');self.assertTrue(cell['manual'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
        reader.mark_complete('2026-09','talon',False)
        reader=MonthlyReader({'talon':self.root},self.today);reader.read();reader.mark_complete('2026-09','talon',True)
        with write(path) as db:db.execute("INSERT INTO jobs VALUES ('nuevo','pending',NULL)")
        self.assertFalse(self.cell(MonthlyReader({'talon':self.root},self.today).read(),'talon')['manual'])

    def test_details_explicit_manual_close_accepts_pending_without_changing_them(self):
        path=self.dua_table(done=False);self.ledger()
        reader=self.reader();reader.read()
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        reader.mark_complete('2026-09','detalles',True)
        cell=self.cell(self.reader().read())
        self.assertEqual(cell['status'],'completed')
        self.assertEqual(cell['label'],'Completado manual')
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)

    def test_manifest_exclusions_and_exhausted_attempts_close_only_finalized_runs(self):
        path=self.manifest('full',pending=True)
        with write(path) as db:
            db.execute('ALTER TABLE jobs ADD COLUMN attempts INTEGER DEFAULT 3')
            db.execute("INSERT INTO partial_pages VALUES ('1')")
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        self.assertEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'completed')
        with write(path) as db:db.execute("UPDATE runs SET state='Detenida'")
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        self.assertNotEqual(reader.cell('2026-09','manifiestos','conocimientos')['status'],'completed')

    def test_manifest_finished_with_exclusions_accepts_legacy_coverage_without_writes(self):
        path=self.manifest('air',mode='aereo',flow='duas')
        with write(path) as db:
            db.execute("INSERT INTO jobs VALUES ('excluded','Excluido')")
            db.execute("UPDATE runs SET state='Finalizada con exclusiones'")
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        self.assertEqual(reader.cell('2026-09','manifiestos','duas')['status'],'completed')
        self.assertEqual(reader.entries[0]['omitted'],1)
        self.assertIn('1 omitidos fuera del resultado final',reader.entries[0]['scope'])
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),digest)
        for change in ("UPDATE runs SET finished=NULL",
                       "UPDATE runs SET state='Detenida',finished='date'",
                       "UPDATE runs SET state='Finalizada con exclusiones'; INSERT INTO jobs VALUES ('pending','Pendiente')"):
            with write(path) as db:db.executescript(change)
            reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
            self.assertNotEqual(reader.cell('2026-09','manifiestos','duas')['status'],'completed')

    def test_manifest_current_month_with_ten_exclusions_is_up_to_date_for_both_modes(self):
        paths=[]
        for mode in ('maritimo','aereo'):
            path=self.manifest(mode,'2026-10-01','2026-10-12',mode=mode,month=10,flow='duas')
            paths.append(path)
            with write(path) as db:
                db.execute('ALTER TABLE jobs ADD COLUMN attempts INTEGER DEFAULT 1')
                if mode=='aereo':
                    db.executemany("INSERT INTO jobs VALUES (?,'Excluido',1)",[(str(n),) for n in range(2,12)])
                    db.execute("UPDATE runs SET state='Finalizada con exclusiones'")
                ids=[r[0] for r in db.execute('SELECT id FROM jobs')]
                signature=hashlib.sha256(json.dumps(sorted(ids),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
                db.executescript('CREATE TABLE workbench_queries(id,start,end,expected,signature,finished);'
                                'CREATE TABLE workbench_query_jobs(query_id,manifest);')
                db.execute('INSERT INTO workbench_queries VALUES (1,?,?,?,?,?)',
                    ('2026-10-01','2026-10-12',len(ids),signature,'date'))
                db.executemany('INSERT INTO workbench_query_jobs VALUES (1,?)',[(mid,) for mid in ids])
        hashes={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        cell=reader.cell('2026-10','manifiestos','duas')
        self.assertEqual(cell['status'],'up_to_date')
        self.assertEqual(cell['displayDays'],12)
        self.assertEqual(sum(e['omitted'] for e in reader.entries),10)
        self.assertEqual({p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},hashes)
        with write(paths[1]) as db:db.execute('UPDATE workbench_queries SET finished=NULL')
        reader=MonthlyReader({'manifiestos':self.root},self.today);reader.read()
        self.assertNotEqual(reader.cell('2026-10','manifiestos','duas')['status'],'up_to_date')


if __name__=='__main__':unittest.main()

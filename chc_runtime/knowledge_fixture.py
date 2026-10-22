"""Preparar SQLite de prueba con el store original. Nunca consulta el portal."""
from datetime import date
from pathlib import Path


def create(root, tag, mode='maritimo', month=9, state='saved', courier=None, start='', end='', limited=False, rows=True, number='20260001'):
    import calendar
    from conocimientos import KnowledgeStore
    from resultados import output_paths
    root=Path(root)
    workspace=root/'data/jobs/conocimientos'/tag
    paths=output_paths({'app_data_folder':str(workspace/'datos_app'),'resultados_folder':str(workspace/'resultados')},
                       'conocimientos',mode,month,2026)
    scope={'version':1,'mode':mode,'month':month,'year':2026,'courier':courier,
           'url':'https://ticaconsultas.hacienda.go.cr/Tica/hcicgmic.aspx',
           'desde':start or f'2026-{month:02d}-01','hasta':end or f'2026-{month:02d}-{calendar.monthrange(2026,month)[1]}',
           'ids':['elegido'] if limited else [],'limit':None}
    mid=f"{dict(maritimo='1',aereo='4',terrestre='7')[mode]}-0-{number}-P027-01/{month:02d}/26"
    store=KnowledgeStore(paths.csv,scope,db_path=paths.database)
    try:
        store.prepare_selection([(1,'',{},mid)] if rows else [])
        store.start_run()
        if rows:
            store.claim(mid)
            if state=='saved':
                records=[[mid,'1','00001234567890123456789','N']+['']*11,
                         [mid,'2','000000000000000000002','S']+['']*11]
                store.save(mid,1,records,{'pages':1,'read':2,'kept':2})
            elif state=='pending':
                store.fail(mid,1,'Error de prueba')
        if state!='active':
            store.finish_run(1 if rows else 0)
    finally:
        store.close()
    return paths.database

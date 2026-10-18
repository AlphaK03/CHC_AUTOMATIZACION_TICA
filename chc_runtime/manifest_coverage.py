"""Cobertura de consultas acumulativas, legible sin importar motores."""
from datetime import date, timedelta
import hashlib
import json


def selection_signature(ids):
    return hashlib.sha256(json.dumps(sorted(ids),ensure_ascii=False,separators=(',',':')).encode()).hexdigest()


def cumulative_days(db, allow_omitted=False):
    """None identifica bases anteriores; una consulta incompleta no aporta días."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE name='workbench_queries'").fetchone():
        return None
    result=set()
    for query_id,start,end,expected,signature in db.execute("SELECT id,start,end,expected,signature FROM workbench_queries WHERE finished IS NOT NULL"):
        ids=[row[0] for row in db.execute('SELECT manifest FROM workbench_query_jobs WHERE query_id=?',(query_id,))]
        if len(ids)!=expected or selection_signature(ids)!=signature:continue
        missing=db.execute('''SELECT 1 FROM workbench_query_jobs q LEFT JOIN jobs j ON j.id=q.manifest
            LEFT JOIN manifests m ON m.id=j.id WHERE q.query_id=? AND (j.id IS NULL OR NOT (
                (j.state='Guardado' AND m.id IS NOT NULL AND NOT EXISTS (
                    SELECT 1 FROM partial_pages p WHERE p.manifest=j.id)) OR
                (? AND (j.state='Excluido' OR (j.state='Pendiente' AND j.attempts>=3))))) LIMIT 1''',
            (query_id,allow_omitted)).fetchone()
        if missing:continue
        current,last=date.fromisoformat(start),date.fromisoformat(end)
        while current<=last:
            result.add(current.isoformat());current+=timedelta(days=1)
    return result


def day_ranges(days):
    ranges=[]
    for day in sorted(days):
        if ranges and date.fromisoformat(day)==date.fromisoformat(ranges[-1][1])+timedelta(days=1):
            ranges[-1]=(ranges[-1][0],day)
        else:ranges.append((day,day))
    return ranges

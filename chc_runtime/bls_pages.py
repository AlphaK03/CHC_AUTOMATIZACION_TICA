"""Páginas BLs verificadas; independientes del éxito final del motor original."""
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sqlite3


@dataclass
class DetailPage:
    form: dict
    state: dict
    columns: list
    rows: list
    offset: int
    eof: bool


def parse_page(html, record, sequence):
    from bs4 import BeautifulSoup
    from core.tables import InvalidResponse, parse_detail
    columns, rows = parse_detail(html, record, sequence)
    soup = BeautifulSoup(html, 'html.parser')
    form = {node['name']:node.get('value','') for node in soup.select('input[name]')
            if node.get('type','').lower() not in ('button','submit','password')}
    state = json.loads(form['GXState'])
    for error in soup.select('#ERROR, [id$="gxErrorViewer"]'):
        if error.get_text(strip=True):
            raise InvalidResponse('TICA devolvió un mensaje en lugar de una página de líneas')
    try:
        if 'GRID1_nEOF' in state or 'GRID1_nFirstRecordOnPage' in state:
            eof, offset = str(state['GRID1_nEOF']), int(state['GRID1_nFirstRecordOnPage'])
            if eof not in ('0','1') or offset < 0 or (not rows and eof!='1'):
                raise ValueError('Estado de paginación incoherente')
            return DetailPage(form,state,columns,rows,offset,eof=='1')
        if soup.select('.PagingButtonsNext'):
            raise ValueError('Paginación sin contador y final verificables')
        return DetailPage(form,state,columns,rows,0,True)
    except (KeyError,TypeError,ValueError) as exc:
        raise InvalidResponse('Página de líneas incompleta: '+str(exc)) from exc


def next_form(page, offset=None):
    state = dict(page.state, _EventName='EGRID1PAGING.', _EventGridId='', _EventRowId='')
    if offset is not None:
        state.update(GRID1_nFirstRecordOnPage=str(offset), GRID1_nEOF='0')
    return dict(page.form, GXState=json.dumps(state), GRID1PAGING='NEXT')


def page_digest(columns, rows):
    return hashlib.sha256(json.dumps([columns,rows],ensure_ascii=False).encode()).hexdigest()


class PageStore:
    def __init__(self, path, signature):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.db = sqlite3.connect(self.path)
        try:
            with self.db:
                self.db.executescript('''CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT);
                    CREATE TABLE IF NOT EXISTS pages (job TEXT, ordinal INTEGER, page INTEGER,
                        offset INTEGER, eof INTEGER, columns_json TEXT, rows_json TEXT,
                        count INTEGER, digest TEXT, PRIMARY KEY(job,page));''')
                self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('signature',?)",(signature,))
                if self.db.execute("SELECT value FROM metadata WHERE key='signature'").fetchone()[0]!=signature:
                    raise ValueError('Las páginas pertenecen a otra selección BLs')
        except BaseException:
            self.db.close()
            raise

    def load(self, job):
        from core.tables import InvalidResponse
        saved, offset, line_ids = [], 0, set()
        for page_number,position,eof,columns,rows,count,digest in self.db.execute(
                'SELECT page,offset,eof,columns_json,rows_json,count,digest FROM pages WHERE job=? ORDER BY page',(job,)):
            columns, rows = json.loads(columns), json.loads(rows)
            if (page_number!=len(saved)+1 or position!=offset or (saved and saved[-1].eof)
                    or len(rows)!=count or page_digest(columns,rows)!=digest or eof not in (0,1)
                    or (not rows and not eof)):
                raise InvalidResponse('El avance por página está incompleto; se conserva para revisión')
            validate_lines(rows,line_ids)
            saved.append(DetailPage({}, {}, columns,rows,position,bool(eof)))
            offset += len(rows)
        return saved

    def save(self, job, ordinal, number, page):
        with self.db:
            self.db.execute('INSERT INTO pages VALUES (?,?,?,?,?,?,?,?,?)',
                (job,ordinal,number,page.offset,int(page.eof),json.dumps(page.columns,ensure_ascii=False),
                 json.dumps(page.rows,ensure_ascii=False),len(page.rows),page_digest(page.columns,page.rows)))

    def finish_repeated_page(self, job, number):
        with self.db:
            self.db.execute('UPDATE pages SET eof=1 WHERE job=? AND page=?',(job,number))

    def close(self):
        self.db.close()


def validate_lines(rows, seen):
    from core.tables import InvalidResponse
    additions = set()
    for row in rows:
        number = row[5].strip()
        if not number.isdigit() or int(number)<1:
            raise InvalidResponse('Línea sin número verificable; BL pendiente')
        key = str(int(number))
        if key in seen or key in additions:
            raise InvalidResponse('Línea repetida entre páginas; BL pendiente')
        additions.add(key)
    seen.update(additions)

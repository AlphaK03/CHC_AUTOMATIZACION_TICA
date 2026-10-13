"""Stage original fields as two half-months or one whole month per regime."""
import calendar

from data_store import MONTHS, REGIMENES
from excel_format import write_excel, empty_columns


def stage_originals(generation, store, period, mode):
    if mode not in ('halves', 'month'):
        raise ValueError('Elige dos quincenas o el mes completo.')
    year, month = map(int, period.split('-'))
    last = calendar.monthrange(year, month)[1]
    month_name = MONTHS[month - 1]
    sheet = month_name.lower() + str(year)[-2:]
    files, pending = {}, {}

    for regimen in REGIMENES:
        queries = store.export_queries(period, regimen)
        saved = [q for q in queries if q['status'] == 'succeeded']
        covered = {day for q in saved for day in range(q['day_start'], q['day_end'] + 1)}
        unresolved = {day for q in queries if q['status'] != 'succeeded'
                      for day in range(q['day_start'], q['day_end'] + 1)}
        missing = sorted((set(range(1, last + 1)) - covered) | unresolved)
        if missing:
            pending[regimen] = missing
        folder = f'{regimen}/{period}'
        prefix = f'DUAS_{month_name}_{regimen}'

        def write(name, rows, unique):
            ids = [q['id'] for q in rows]
            # Match legacy DataFrame column discovery/order, including optional
            # fields. A second streaming pass writes data without loading a month.
            columns = dict()
            for record in store.export_records(ids):
                columns.update(dict.fromkeys(record))
            columns = list(columns) or list(empty_columns(regimen))
            records = store.export_records(ids, unique=unique)
            files[name] = write_excel(generation / name, sheet, columns,
                                     ([record.get(column, '') for column in columns] for record in records))

        if mode == 'month':
            if not missing:
                write(f'{folder}/{prefix}_{year}.xlsx', saved, True)
        else:
            for first, end in ((1, 15), (16, last)):
                rows = [q for q in saved if first <= q['day_start'] <= q['day_end'] <= end]
                days = {day for q in rows for day in range(q['day_start'], q['day_end'] + 1)}
                wanted = set(range(first, end + 1))
                if wanted <= days and not wanted & unresolved:
                    write(f'{folder}/{prefix}_{first}-{end}.xlsx', rows, True)
                else:
                    pending.setdefault(regimen, [])
                    pending[regimen] = sorted(set(pending[regimen]) | (wanted - days) | (wanted & unresolved))
    return files, pending

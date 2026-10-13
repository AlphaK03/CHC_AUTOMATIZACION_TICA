"""Persistencia atómica de todas las filas de un DUA, reutilizable entre bots."""
import logging

from .identifiers import normalize_dua
from .job_store import JobStore, atomic_output


class MultiRowJobStore(JobStore):
    fields = ()

    @classmethod
    def validate_rows(cls, rows, expected):
        expected = normalize_dua(expected)
        if not rows:
            raise ValueError('No hay filas confirmadas para el DUA.')
        for row in rows:
            if set(row) != set(cls.fields) or any(not isinstance(value, str) for value in row.values()):
                raise ValueError('El resultado no contiene todas las columnas del módulo.')
            if normalize_dua(row['numero_del_dua']) != expected:
                raise ValueError('Una fila no corresponde al DUA solicitado.')
            row['numero_del_dua'] = expected
        return rows

    def complete(self, job, result):
        rows = self.validate_rows(result.get('rows', []), job['dua'])
        super().complete(job, {**rows[0], 'rows': rows})

    def result_rows(self, result):
        return self.validate_rows(result.get('rows', []), result['numero_del_dua'])

    def migrate_csv(self, path, fields):
        if path:
            logging.info('CSV anterior conservado como referencia; no acredita todas las filas del DUA.')
        return 0

    def export(self, paths, fields):
        super().export(paths, fields)
        if 'no_rows_duas' in paths:
            with self.lock, atomic_output(paths['no_rows_duas']) as stream:
                for row in self.db.execute("SELECT dua FROM jobs WHERE status!='succeeded' "
                                           "AND error_kind IN ('NoRowsException','NoMovimientosError')"):
                    stream.write(row[0] + '\n')

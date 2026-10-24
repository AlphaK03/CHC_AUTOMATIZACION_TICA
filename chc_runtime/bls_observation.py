"""Conteos de observación BLs por modalidad, sin modificar trabajos ni resultados."""

MODES = {'maritimo':'Marítimo', 'aereo':'Aéreo', 'terrestre':'Terrestre', '':'Sin modalidad'}
KEYS = ('total','succeeded','pending','running','invalid','excluded','rows','empty')
STATES = {'Guardado':'succeeded', 'Pendiente':'pending', 'Descargando':'running',
          'Inválido':'invalid', 'Excluido':'excluded'}


def manifest_mode(manifest):
    return {'1':'maritimo','4':'aereo','7':'terrestre'}.get(str(manifest).split('-')[0], '')


def combine(summaries):
    grouped = {}
    for summary in summaries:
        mode = summary['mode']
        target = grouped.setdefault(mode, dict(mode=mode, label=MODES[mode], **dict.fromkeys(KEYS,0)))
        for key in KEYS:
            target[key] += summary.get(key,0)
    return [grouped[mode] for mode in MODES if mode in grouped]


class BlsModeProgress:
    def __init__(self):
        self.jobs = {}
        self.counts = {}

    @classmethod
    def read(cls, db):
        result = cls()
        for ordinal,manifest,state,rows in db.execute('''SELECT ordinal,
                json_extract(payload,'$."IDManifiesto"'),state,result_count FROM jobs'''):
            result.update(dict(ordinal=ordinal,manifest=manifest,state=state,result_count=rows))
        return result

    def contribution(self, job, sign):
        mode,state,rows = job
        counts = self.counts.setdefault(mode,dict.fromkeys(KEYS,0))
        counts['total'] += sign
        counts[STATES.get(state,'pending')] += sign
        if state == 'Guardado':
            counts['rows'] += sign * rows
            counts['empty'] += sign * int(rows == 0)

    def update(self, event):
        ordinal = event['ordinal']
        current = (manifest_mode(event.get('manifest','')),event['state'],event.get('result_count',0))
        previous = self.jobs.get(ordinal)
        if previous == current:
            return
        if previous is not None:
            self.contribution(previous,-1)
        self.jobs[ordinal] = current
        self.contribution(current,1)

    def summaries(self, processing=True):
        result = []
        for mode in MODES:
            if mode not in self.counts or not self.counts[mode]['total']:
                continue
            stats = dict(mode=mode,label=MODES[mode],**self.counts[mode])
            if not processing:
                stats['pending'] += stats['running']
                stats['running'] = 0
            result.append(stats)
        return result

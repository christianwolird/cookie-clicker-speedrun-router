"""Read a compact snapshot of the final session's running searches."""
from datetime import datetime, timezone
import json
from experiment_paths import WORK


def read_rows(path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass  # A writer may be appending the last record.
    return rows


archive = read_rows(WORK / 'final_archive_results.jsonl')
runs = [run for row in archive for run in row['refinements']]
crossovers = []
for path in sorted(WORK.glob('final_crossover_[0-9][0-9].jsonl')):
    rows = read_rows(path)
    if rows:
        crossovers.append(dict(name=path.stem, **{key:rows[-1][key] for key in
            ('event', 'finish', 'current', 'elapsed', 'tried') if key in rows[-1]}))
canonical = []
for name in ('canonical_order3', 'canonical_order4', 'canonical_deletion4',
             'canonical_cube', 'canonical_order5_mid', 'canonical_order5_tail', 'canonical_order5_earlier'):
    rows = read_rows(WORK / (name+'.jsonl'))
    if rows:
        canonical.append(dict(name=name, **{key:rows[-1][key] for key in
            ('event', 'finish', 'elapsed', 'tried', 'next_index') if key in rows[-1]}))
print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
    global_best=json.loads((WORK / 'session_best.json').read_text())['finish'],
    archive=dict(completed=len(archive), total=1014,
                 trials=sum(run['tried'] for run in runs),
                 best=min((run['finish'] for run in runs), default=None),
                 finished=(WORK / 'final_archive_results.json').exists()),
    crossovers=crossovers, canonical_checks=canonical)))

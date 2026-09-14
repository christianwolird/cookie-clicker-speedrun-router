"""Briefly refine each distinct beam-batching result under the trained profile."""
import json
from pathlib import Path
import subprocess
import sys

from experiment_paths import WORK

here = Path(__file__).resolve().parent
rows = []
for i, source in enumerate(('prefetch_batch_3', 'prefetch_batch_6', 'prefetch_batch_12',
                            'prefetch_timed_3', 'prefetch_timed_12')):
    for locked in (True, False):
        name = source + ('_locked' if locked else '_open')
        command = [sys.executable, str(here / 'run_native_local.py'), name,
                   '--source', str(WORK / (source+'.route')), '--seconds', '20',
                   '--width', '4', '--seed', str(31000+2*i+int(locked)),
                   '--tmax', '.4' if locked else '.8', '--tmin', '.001',
                   '--cycle', '20000', '--blocks', '--cache-size', '100000']
        if locked:
            command.append('--lock-upgrades')
        with (WORK / (name+'.log')).open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        row = json.loads((WORK / (name+'.json')).read_text())
        rows.append(row)
        (WORK / 'prefetch_refinement.json').write_text(json.dumps(rows, indent=2)+'\n')
        print(json.dumps(dict(name=name, finish=row['finish'], tried=row['last']['tried'])), flush=True)

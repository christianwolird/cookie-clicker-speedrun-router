"""Cover the dense six-or-more-change neighborhood after prior scans finish."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

from experiment_paths import WORK

here = Path(__file__).resolve().parent
deadline = datetime.fromisoformat('2026-09-14T14:15:00+00:00').timestamp()
stop = WORK / 'quantity_cube_suite.stop'
lease = (WORK / 'quantity_cube_suite.lock').open('a')
fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
while True:
    if stop.exists() or time.time() >= deadline:
        raise SystemExit(0)
    try:
        if json.loads((WORK / 'combined_neighborhood_coverage.json').read_text())['complete']:
            break
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    time.sleep(5)

total = 25380504


def run(index):
    if stop.exists() or time.time() >= deadline:
        return None
    begin, end = total*index//8, total*(index+1)//8
    name = f'quantity_cube_{index:02d}'
    command = [sys.executable, str(here / 'run_native_local.py'), name,
               '--source', str(WORK / 'quantity_scan_best_5_source.route'),
               '--seconds', str(max(1, deadline-time.time())), '--width', '4',
               '--quantity-cube-minimum', '6', '--quantity-start', str(begin),
               '--quantity-end', str(end)]
    with (WORK / f'{name}.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    row = json.loads((WORK / f'{name}.json').read_text())
    assert row['last']['total_combinations'] == total
    return row


results = []
with ThreadPoolExecutor(max_workers=2) as pool:
    for future in as_completed([pool.submit(run, i) for i in range(8)]):
        row = future.result()
        if row:
            results.append(row)
            print(json.dumps(dict(name=row['name'], finish=row['finish'], tried=row['last']['tried'],
                                  complete=row['last']['range_finished'])), flush=True)
rows = sorted(results, key=lambda row: row['last']['range_start'])
cursor = 0
for row in rows:
    final = row['last']
    assert final['range_start'] == cursor
    assert final['tried'] == final['next_index']-cursor
    cursor = final['next_index']
summary = dict(finished_utc=datetime.now(timezone.utc).isoformat(), total=total,
               covered=cursor, complete=cursor == total, trials=rows,
               scope='Fixed original sequence; quantities within one of original, at least six changes, width four')
(WORK / 'quantity_cube_suite.json').write_text(json.dumps(summary, indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k != 'trials'}), flush=True)

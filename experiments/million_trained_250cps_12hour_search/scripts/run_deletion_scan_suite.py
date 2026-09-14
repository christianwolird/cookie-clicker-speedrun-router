"""Scan mixed quantity/deletion neighborhoods as policy workers become free."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

from experiment_paths import WORK

p = argparse.ArgumentParser()
p.add_argument('--shard', type=int, choices=(0, 1), required=True)
p.add_argument('--until', default='2026-09-14T14:15:00+00:00')
args = p.parse_args()
deadline = datetime.fromisoformat(args.until).timestamp()
here = Path(__file__).resolve().parent
stop = WORK / f'deletion_scan_suite_{args.shard}.stop'
completed = WORK / f'policy_ensemble_suite_{args.shard}.json'
while True:
    if stop.exists() or time.time() >= deadline:
        raise SystemExit(0)
    try:
        if len(json.loads(completed.read_text())) == 2:
            break
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    time.sleep(5)

# All scans use the same original normalized sequence, even if a better output
# is discovered. The two order-five ranges are disjoint in deletion-only space.
trials = []
if args.shard == 0:
    trials += [(f'deletion_order{k}', k, 0, 2**64-1) for k in (1, 2, 4)]
    trials.append(('deletion_order5_a', 5, 0, 126702394))
else:
    trials.append(('deletion_order5_b', 5, 126702394, 253404788))
results = []
for name, order, begin, end in trials:
    if stop.exists() or time.time() >= deadline:
        break
    command = [sys.executable, str(here / 'run_native_local.py'), name,
               '--source', str(WORK / 'quantity_scan_best_5_source.route'),
               '--seconds', str(max(1, deadline-time.time())), '--width', '4',
               '--quantity-order', str(order), '--quantity-deletions',
               '--quantity-start', str(begin), '--quantity-end', str(end)]
    with (WORK / f'{name}.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    row = json.loads((WORK / f'{name}.json').read_text())
    results.append(row)
    (WORK / f'deletion_scan_suite_{args.shard}.json').write_text(json.dumps(results, indent=2)+'\n')
    print(json.dumps(dict(name=name, finish=row['finish'], tried=row['last']['tried'],
                          next_index=row['last']['next_index'], range_finished=row['last']['range_finished'])), flush=True)

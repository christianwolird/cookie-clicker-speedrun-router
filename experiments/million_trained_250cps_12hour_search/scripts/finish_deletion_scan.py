"""Use one freed worker, then split the remaining fixed-source range over two."""
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

from experiment_paths import WORK

here = Path(__file__).resolve().parent
deadline = datetime.fromisoformat('2026-09-14T14:15:00+00:00').timestamp()
stop = WORK / 'finish_deletion_scan.stop'
total = 253404788


def free_workers():
    first = (WORK / 'deletion_order5_a.json').exists()
    try:
        second = len(json.loads((WORK / 'policy_ensemble_suite_1.json').read_text())) == 2
    except (FileNotFoundError, json.JSONDecodeError):
        second = False
    return int(first) + int(second)


def launch(name, begin, end):
    command = [sys.executable, str(here / 'run_native_local.py'), name,
               '--source', str(WORK / 'quantity_scan_best_5_source.route'),
               '--seconds', str(max(1, deadline-time.time())), '--width', '4',
               '--quantity-order', '5', '--quantity-deletions',
               '--quantity-start', str(begin), '--quantity-end', str(end)]
    with (WORK / f'{name}.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    print(json.dumps(dict(event='started', name=name, begin=begin, end=end)), flush=True)
    return process


while not free_workers():
    if stop.exists() or time.time() >= deadline:
        raise SystemExit(0)
    time.sleep(5)

name = 'deletion_order5_b'
if (WORK / f'{name}.json').exists() or (WORK / f'{name}.jsonl').exists():
    raise SystemExit('Existing second-range trial; refusing to overwrite it')
process = launch(name, 126702394, total)
while process.poll() is None and free_workers() < 2 and not stop.exists() and time.time() < deadline:
    time.sleep(5)
if process.poll() is None:
    (WORK / f'{name}.stop').touch()
if process.wait():
    raise SystemExit('First range worker failed')
row = json.loads((WORK / f'{name}.json').read_text())
begin = row['last']['next_index']
print(json.dumps(dict(event='first_worker_finished', next_index=begin)), flush=True)
if begin < total and not stop.exists() and time.time() < deadline:
    middle = (begin + total) // 2
    jobs = [(f'deletion_order5_resume_{suffix}', start, end) for suffix, start, end in
            [('a', begin, middle), ('b', middle, total)]]
    running = [(name, launch(name, start, end)) for name, start, end in jobs]
    while any(process.poll() is None for _, process in running):
        if stop.exists() or time.time() >= deadline:
            for name, _ in running:
                (WORK / f'{name}.stop').touch()
        time.sleep(5)
    for name, process in running:
        if process.wait():
            raise SystemExit(f'{name} failed')
subprocess.run([sys.executable, str(here / 'verify_neighborhood_coverage.py'),
                '--require-complete'], check=True)

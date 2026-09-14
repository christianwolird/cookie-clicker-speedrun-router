"""Spend a bounded parallel budget refining newly harvested long-beam routes."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import subprocess
import sys
import time

from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT / 'src'))
from native_bridge import pack_actions
from ccsr.routes import execute_route, load_route

p = argparse.ArgumentParser()
p.add_argument('--workers', type=int, default=10)
p.add_argument('--until', default='2026-09-14T13:50:00+00:00')
args = p.parse_args()
if args.workers < 1:
    p.error('workers must be positive')
deadline = datetime.fromisoformat(args.until).timestamp()
here = Path(__file__).resolve().parent
lease = (WORK / 'final_archive_controller.lock').open('a')
fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
stop = WORK / 'final_archive_controller.stop'
names = ('long_root_forecast', 'long_wide_diverse', 'long_upgrade_bonus',
         'long_inventory_restricted')
while not all((WORK / f'{name}.json').exists() for name in names):
    if stop.exists() or time.time() >= deadline:
        raise SystemExit(0)
    time.sleep(5)

def flattened(plan):
    return tuple(int(code) for errand in plan.errands for code in pack_actions(errand))

previous = set()
old_manifest = WORK / 'counts_archive_manifest.json'
if old_manifest.exists():
    for row in json.loads(old_manifest.read_text()):
        previous.add(flattened(load_route(row['path'])))
unique = {}
observed = 0
for name in names:
    for path in sorted((WORK / f'{name}_candidates').glob('*.route')):
        plan = load_route(path)
        key = flattened(plan)
        score = execute_route(plan).final_gamestate.age
        observed += 1
        if key not in unique or score < unique[key]['finish']:
            unique[key] = dict(path=str(path), finish=score, already_refined=key in previous,
                               upgrade_order=[code for code in key if code >= 256])
seeds = sorted(unique.values(), key=lambda row: (row['already_refined'], row['finish'], row['path']))
seconds = max(2, min(30, int(max(0, deadline-time.time())*.9*args.workers/max(1, 2*len(seeds)))))
manifest = dict(utc=datetime.now(timezone.utc).isoformat(), sources=names,
                observed=observed, unique=len(seeds), previously_refined=sum(row['already_refined'] for row in seeds),
                workers=args.workers, seconds_per_refinement=seconds, deadline=args.until, seeds=seeds)
(WORK / 'final_archive_manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
print(json.dumps({k: v for k, v in manifest.items() if k != 'seeds'}), flush=True)

def refine(index, seed):
    rows = []
    source = seed['path']
    for locked in (True, False):
        if stop.exists() or time.time() >= deadline:
            break
        name = f'final_archive_{index:04d}_' + ('locked' if locked else 'open')
        command = [sys.executable, str(here / 'run_native_local.py'), name,
                   '--source', source, '--seconds', str(min(seconds, max(1, deadline-time.time()))),
                   '--width', '4', '--seed', str(26000+index*2+int(locked)),
                   '--tmax', '.4' if locked else '.8', '--tmin', '.001',
                   '--cycle', '20000', '--blocks', '--cache-size', '100000',
                   '--restart-best', '.5']
        if locked:
            command.append('--lock-upgrades')
        with (WORK / f'{name}.log').open('w') as log:
            subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
        row = json.loads((WORK / f'{name}.json').read_text())
        rows.append(dict(name=name, finish=row['finish'], elapsed=row['elapsed'],
                         tried=row['last']['tried'], route=row['route'], locked=locked))
        source = row['route']
    return dict(index=index, source=seed, refinements=rows)

results = []
with ThreadPoolExecutor(max_workers=args.workers) as pool:
    futures = [pool.submit(refine, i, seed) for i, seed in enumerate(seeds)]
    for future in as_completed(futures):
        row = future.result()
        results.append(row)
        with (WORK / 'final_archive_results.jsonl').open('a') as log:
            log.write(json.dumps(row)+'\n')
        scores = [r['finish'] for r in row['refinements']]
        print(json.dumps(dict(index=row['index'], completed=len(results), total=len(seeds),
                              finish=min(scores) if scores else None)), flush=True)
summary = dict(manifest=str(WORK / 'final_archive_manifest.json'),
               finished_utc=datetime.now(timezone.utc).isoformat(), results=results)
(WORK / 'final_archive_results.json').write_text(json.dumps(summary, indent=2)+'\n')

"""Use the remaining session budget for mixed-strategy route crossovers."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT / 'src'))
from ccsr.routes import execute_route, load_route
from native_bridge import pack_actions

here = Path(__file__).resolve().parent
deadline = datetime.fromisoformat('2026-09-14T14:20:00+00:00').timestamp()
stop = WORK / 'final_crossover_controller.stop'
lease = (WORK / 'final_crossover_controller.lock').open('a')
fcntl.flock(lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
while not (WORK / 'final_archive_results.json').exists():
    if stop.exists() or time.time() >= deadline-30:
        raise SystemExit(0)
    time.sleep(5)

manifest = json.loads((WORK / 'final_archive_manifest.json').read_text())
archive = json.loads((WORK / 'final_archive_results.json').read_text())
paths = [Path(row['path']) for row in manifest['seeds']]
paths += [Path(run['route']) for row in archive['results'] for run in row['refinements']]
unique = {}
for path in paths:
    plan = load_route(path)
    key = tuple(int(c) for e in plan.errands for c in pack_actions(e))
    score = execute_route(plan).final_gamestate.age
    if key not in unique or score < unique[key][0]:
        unique[key] = (score, path)
directory = WORK / 'final_crossover_seeds'
directory.mkdir(exist_ok=True)
for i, (_, path) in enumerate(sorted(unique.values())):
    shutil.copyfile(path, directory / f'seed_{i:04d}.route')
source = WORK / 'final_crossover_source.route'
shutil.copyfile(WORK / 'session_best.route', source)
configs = [
    dict(tmax=.2, cycle=200000, restart_best=.2),
    dict(tmax=.8, cycle=200000, restart_best=0),
    dict(tmax=2, cycle=500000, restart_best=0),
    dict(tmax=4, cycle=1000000, restart_best=0),
    dict(tmax=.8, cycle=200000, restart_best=.2, errand_bias=.05, action_bias=.02),
    dict(tmax=.8, cycle=200000, restart_best=.2, errand_bias=-.05, action_bias=-.02),
    dict(tmax=.8, cycle=200000, restart_best=.2, aggregate_partition=True, max_size=64),
    dict(tmax=.4, cycle=100000, restart_best=.2, aggregate_partition=True, expand=True, max_size=128),
]
metadata = dict(started_utc=datetime.now(timezone.utc).isoformat(), deadline_utc='2026-09-14T14:20:00+00:00',
                pool=len(unique), source=str(source), configurations=configs)
(WORK / 'final_crossover_manifest.json').write_text(json.dumps(metadata, indent=2)+'\n')
print(json.dumps(metadata), flush=True)


def run(index, config):
    if stop.exists() or time.time() >= deadline-30:
        return None
    name = f'final_crossover_{index:02d}'
    command = [sys.executable, str(here / 'run_native_local.py'), name,
               '--source', str(source), '--extra-directory', str(directory),
               '--seconds', str(max(1, deadline-time.time()-20)), '--seed', str(81000+index),
               '--width', '4', '--tmin', '.001', '--blocks', '--cache-size', '100000']
    for key, value in config.items():
        command.append('--'+key.replace('_', '-'))
        if value is not True:
            command.append(str(value))
    with (WORK / f'{name}.log').open('w') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    result = json.loads((WORK / f'{name}.json').read_text())
    print(json.dumps(dict(name=name, finish=result['finish'], tried=result['last']['tried'])), flush=True)
    return result


results = []
with ThreadPoolExecutor(max_workers=8) as pool:
    for future in as_completed([pool.submit(run, i, config) for i, config in enumerate(configs)]):
        result = future.result()
        if result:
            results.append(result)
summary = dict(finished_utc=datetime.now(timezone.utc).isoformat(), metadata=metadata, results=results)
(WORK / 'final_crossover_results.json').write_text(json.dumps(summary, indent=2)+'\n')

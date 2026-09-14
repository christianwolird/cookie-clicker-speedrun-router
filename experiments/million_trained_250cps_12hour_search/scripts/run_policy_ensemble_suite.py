"""Try several from-scratch policies after a quantity worker becomes free."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

from experiment_paths import WORK

p = argparse.ArgumentParser()
p.add_argument('--shard', type=int, choices=(0, 1), required=True)
p.add_argument('--after', required=True)
args = p.parse_args()
here = Path(__file__).resolve().parent
stop = WORK / f'policy_ensemble_suite_{args.shard}.stop'
while not (WORK / f'{args.after}.json').exists():
    if stop.exists():
        raise SystemExit(0)
    time.sleep(5)

common = dict(pool=1200, inner=1500, pops=5000, mode=2)
trials = [
    ('bonuses', {'rollout-width': 40, 'rollout-inner': 100, 'rollout-pops': 300,
                 'rollout-bonuses': '0,0.05,0.1,0.2'}),
    ('wide', {'pool': 3000, 'inner': 4000, 'pops': 15000, 'rollout-width': 80,
              'rollout-inner': 200, 'rollout-pops': 600, 'rollout-bonuses': '0,0.1'}),
    ('outer_bonus', {'upgrade-bonus': 0.1, 'rollout-width': 40, 'rollout-inner': 100,
                    'rollout-pops': 300, 'rollout-bonuses': '0,0.05,0.1,0.2'}),
    ('strong_rollout', {'pool': 1600, 'inner': 2000, 'pops': 8000,
                       'rollout-width': 160, 'rollout-inner': 400,
                       'rollout-pops': 1200, 'rollout-bonuses': '0,0.1'}),
]
rows = []
for i, (suffix, additions) in enumerate(trials):
    if i % 2 != args.shard or stop.exists():
        continue
    name = f'policy_ensemble_{suffix}'
    with (WORK / f'{name}.log').open('w') as log:
        subprocess.run([sys.executable, str(here / 'run_native_policy.py'), name,
                        '--seconds', '1800', '--options-json', json.dumps(dict(common, **additions))],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    result = {'name': name, 'greedy': json.loads((WORK / f'{name}.json').read_text())}
    for locked in (True, False):
        refined = name + ('_locked' if locked else '_open')
        cmd = [sys.executable, str(here / 'run_native_local.py'), refined,
               '--source', str(WORK / f'{name}.route'), '--seconds', '180',
               '--width', '4', '--seed', str(21000 + 2*i + int(locked)),
               '--tmax', '.4' if locked else '.8', '--tmin', '.001',
               '--cycle', '20000', '--blocks', '--cache-size', '100000']
        if locked:
            cmd.append('--lock-upgrades')
        with (WORK / f'{refined}.log').open('w') as log:
            subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, check=True)
        result['locked' if locked else 'open'] = json.loads((WORK / f'{refined}.json').read_text())
    rows.append(result)
    (WORK / f'policy_ensemble_suite_{args.shard}.json').write_text(json.dumps(rows, indent=2) + '\n')
    print(json.dumps({key: (value['finish'] if isinstance(value, dict) else value)
                      for key, value in result.items()}), flush=True)

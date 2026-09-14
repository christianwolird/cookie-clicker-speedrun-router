"""Compare inventory forecasts from the same greedy ruler and initial state."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from experiment_paths import WORK

p = argparse.ArgumentParser(); p.add_argument('--wait-for'); p.add_argument('--seconds', type=int, default=600)
args = p.parse_args(); here = Path(__file__).resolve().parent; work = WORK
if args.wait_for:
    while not Path(args.wait_for).exists(): time.sleep(2)
common = dict(width=2000, inner=2000, pops=6000, workers=2, horizon=0, anchor=4,
              macro=1, order=1, prune=.94, heap=300000, nodes=3000000, compact=1, harvest=128)
common.update({'future-mask':32768, 'canonical-partials':1, 'quantity-children':4,
               'age-bound':1, 'seed-prefixes':0, 'persistent-workers':1, 'stage-balance':1,
               'hand-dominance':1, 'rollout-weight':.5, 'hint-slack':1, 'target-rollout':1,
               'retain-closed':1, 'harvest-strategy':1, 'harvest-slack':4, 'report-generated':1,
               'rollout-keep':160, 'rollout-raw':40, 'completion-cache':100000})
results = []
for label, fraction in (('000',0), ('003',.03), ('010',.1), ('020',.2), ('040',.4), ('010_bonus',.1)):
    name = 'param_forecast_greedy_' + label
    options = dict(common, **{'future-inventory':fraction})
    if label.endswith('bonus'): options['upgrade-bonus'] = .1
    with (work / f'{name}.log').open('w') as log:
        subprocess.run([sys.executable, str(here/'run_native_beam.py'), name,
                        '--source', str(work/'greedy_native_three3000_mouse.route'),
                        '--seconds', str(args.seconds), '--options-json', json.dumps(options)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    result = json.loads((work/f'{name}.json').read_text()); results.append(result)
    print(json.dumps(result), flush=True)
    (work/'parameter_c_results.json').write_text(json.dumps(results, indent=2)+'\n')

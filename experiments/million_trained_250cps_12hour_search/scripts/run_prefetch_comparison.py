"""Compare whole-beam prefetch sizes at the same outer expansion budget."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from experiment_paths import WORK

here = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('--seconds', type=float, default=900)
p.add_argument('--expansions', type=int, default=6000)
p.add_argument('--sizes', default='3,6,12')
p.add_argument('--prefix', default='prefetch_batch')
args = p.parse_args()
common = dict(workers=3, width=600, inner=800, pops=2000, horizon=0, anchor=4,
              macro=1, order=1, prune=.9, heap=300000, nodes=3000000, compact=1)
common.update({'persistent-workers': 1, 'stage-balance': 1, 'seed-prefixes': 0,
               'future-mask': 32768, 'future-inventory': .03, 'canonical-partials': 1,
               'quantity-children': 4, 'target-rollout': 1, 'rollout-weight': .5,
               'hint-slack': 1.5, 'rollout-keep': 80, 'rollout-raw': 20,
               'completion-cache': 100000, 'retain-closed': 1, 'age-bound': 1,
               'report-generated': 1, 'expansions': args.expansions})
rows = []
for size in map(int, args.sizes.split(',')):
    name = f'{args.prefix}_{size}'
    options = dict(common, **{'batch-size': size})
    with (WORK / f'{name}.log').open('w') as log:
        subprocess.run([sys.executable, str(here / 'run_native_beam.py'), name,
                        '--source', str(WORK / 'optimized_recipe_greedy.route'),
                        '--seconds', str(args.seconds), '--options-json', json.dumps(options)],
                       stdout=log, stderr=subprocess.STDOUT, check=True)
    row = json.loads((WORK / f'{name}.json').read_text())
    rows.append(row)
    summary = 'prefetch_comparison' if args.prefix == 'prefetch_batch' else args.prefix+'_comparison'
    (WORK / (summary+'.json')).write_text(json.dumps(rows, indent=2)+'\n')
    print(json.dumps({key: row[key] for key in ('name', 'finish', 'direct_finish', 'elapsed', 'cpu_seconds')}), flush=True)

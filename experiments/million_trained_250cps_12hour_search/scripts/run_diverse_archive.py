"""Collect near misses with several shapes per upgrade order."""
import json
from pathlib import Path
import subprocess
import sys
import time
from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT/'src'))
from ccsr.routes import load_route, execute_route
from native_bridge import pack_actions

here = Path(__file__).resolve().parent; work = WORK
while not all((work/f'new_cached_order_{i:03d}.json').exists() for i in (161,162)): time.sleep(2)
name = 'diverse_counts_archive'
options = dict(width=1200, inner=1500, pops=5000, workers=2, horizon=0, anchor=4,
               macro=1, order=.99, prune=.90, heap=300000, nodes=3000000, compact=1, harvest=512)
options.update({'future-mask':32768, 'future-inventory':.1, 'canonical-partials':1,
                'quantity-children':4, 'age-bound':1, 'start-prefix':4, 'seed-prefixes':0,
                'persistent-workers':1, 'stage-balance':1, 'hand-dominance':1,
                'rollout-weight':.5, 'hint-slack':4, 'target-rollout':1,
                'retain-closed':1, 'harvest-strategy':3, 'harvest-order-limit':8,
                'harvest-slack':8, 'report-generated':1, 'rollout-keep':160,
                'rollout-raw':40, 'completion-cache':100000})
with (work/f'{name}.log').open('w') as log:
    subprocess.run([sys.executable, str(here/'run_native_beam.py'), name,
                    '--source', str(work/'session_best.route'), '--seconds', '900',
                    '--options-json', json.dumps(options)], stdout=log, stderr=subprocess.STDOUT, check=True)
distinct = {}
for path in sorted((work/f'{name}_candidates').glob('*.route')):
    plan = load_route(path); flat = tuple(code for e in plan.errands for code in pack_actions(e))
    finish = execute_route(plan).final_gamestate.age
    if flat not in distinct or finish < distinct[flat]['finish']:
        distinct[flat] = dict(path=str(path), finish=finish, upgrade_order=[c for c in flat if c>=256])
manifest = sorted(distinct.values(), key=lambda r:r['finish'])
pending = work/'counts_archive_manifest.pending.json'; pending.write_text(json.dumps(manifest, indent=2)+'\n')
pending.replace(work/'counts_archive_manifest.json')
print(json.dumps(dict(seeds=len(manifest), upgrade_orders=len({tuple(r['upgrade_order']) for r in manifest}))), flush=True)

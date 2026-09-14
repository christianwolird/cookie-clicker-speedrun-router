"""Compare inventory restrictions from one fixed, replay-verified source."""
import json
from pathlib import Path
import subprocess
import sys

from experiment_paths import WORK

here = Path(__file__).resolve().parent
source = WORK / 'inventory_cap_comparison_source.route'
source.write_bytes((WORK / 'session_best.route').read_bytes())
common = dict(width=1200, inner=2000, pops=6000, workers=2, horizon=0,
              anchor=4, macro=1, order=1, prune=.9, heap=300000, nodes=3000000,
              compact=1, harvest=192)
common.update({'future-mask': 32768, 'future-inventory': .03,
               'canonical-partials': 1, 'quantity-children': 4,
               'age-bound': 1, 'seed-prefixes': 0, 'persistent-workers': 1,
               'stage-balance': 1, 'hand-dominance': 1, 'rollout-weight': .5,
               'hint-slack': 1.5, 'target-rollout': 1, 'retain-closed': 1,
               'harvest-strategy': 3, 'harvest-order-limit': 4,
               'harvest-slack': 4, 'report-generated': 1,
               'rollout-keep': 320, 'rollout-raw': 80,
               'completion-cache': 100000, 'refresh-hints': 1})
results = []
for suffix, slack, upgrades in [('none', -1, 0), ('exact', 0, 0),
                                 ('exact_upgrades', 0, 1), ('plus3', 3, 0),
                                 ('plus8', 8, 0)]:
    name = 'inventory_cap_' + suffix
    options = dict(common, **{'inventory-cap': slack, 'upgrade-cap': upgrades})
    with (WORK / (name + '.log')).open('w') as output:
        subprocess.run([sys.executable, str(here / 'run_native_beam.py'), name,
                        '--source', str(source), '--seconds', '300',
                        '--options-json', json.dumps(options)],
                       stdout=output, stderr=subprocess.STDOUT, check=True)
    result = json.loads((WORK / (name + '.json')).read_text())
    results.append(result)
    (WORK / 'inventory_cap_results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(name, result['finish'], result['last']['expanded'], flush=True)

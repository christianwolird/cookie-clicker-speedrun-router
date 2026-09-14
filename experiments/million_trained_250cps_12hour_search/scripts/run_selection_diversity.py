"""Compare a modest diversity reservation after a wide errand search."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
from experiment_paths import WORK

work=WORK;here=Path(__file__).resolve().parent;results=[]
source=work/'diversity_selection_source.route';shutil.copyfile(work/'session_best.route',source)
common=dict(width=5000,inner=3000,pops=10000,workers=1,horizon=0,anchor=4,macro=1,
            order=1,prune=.90,heap=300000,nodes=3000000,compact=1,harvest=128)
common.update({'future-mask':32768,'future-inventory':.1,'canonical-partials':1,
               'quantity-children':4,'strategy-bins':2,'age-bound':1,'start-prefix':4,
               'seed-prefixes':0,'persistent-workers':1,'stage-balance':1,'hand-dominance':1,
               'rollout-weight':.5,'hint-slack':1,'target-rollout':1,'retain-closed':1,
               'harvest-strategy':3,'harvest-order-limit':4,'harvest-slack':4,
               'report-generated':1,'rollout-keep':160,'rollout-raw':40,
               'completion-cache':100000,'refresh-hints':1})
for count in (0,40):
    name=f'selection_diversity_{count}';options=dict(common,**{'rollout-diverse':count})
    with (work/f'{name}.log').open('w') as log:
        subprocess.run([sys.executable,str(here/'run_native_beam.py'),name,'--source',str(source),
                        '--seconds','900','--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
    row=json.loads((work/f'{name}.json').read_text());results.append(row);print(json.dumps(row),flush=True)
    (work/'selection_diversity_results.json').write_text(json.dumps(results,indent=2)+'\n')

"""Test queued completion-hint refresh after dynamic-ruler improvements."""
import json
from pathlib import Path
import subprocess
import sys
from experiment_paths import WORK

work=WORK;here=Path(__file__).resolve().parent;results=[]
common=dict(width=1200,inner=1500,pops=5000,workers=1,horizon=0,anchor=4,macro=1,
            order=1,prune=.94,heap=200000,nodes=2000000,compact=1,harvest=64,expansions=8000)
common.update({'future-mask':32768,'future-inventory':.1,'canonical-partials':1,
               'quantity-children':4,'age-bound':1,'seed-prefixes':0,'persistent-workers':1,
               'stage-balance':1,'hand-dominance':1,'rollout-weight':.5,'hint-slack':1,
               'target-rollout':1,'retain-closed':1,'harvest-strategy':1,'harvest-slack':4,
               'report-generated':1,'rollout-keep':160,'rollout-raw':40,'completion-cache':100000})
for enabled in (0,1):
    name=f'refresh_from_greedy_{enabled}';options=dict(common,**{'refresh-hints':enabled})
    with (work/f'{name}.log').open('w') as log:
        subprocess.run([sys.executable,str(here/'run_native_beam.py'),name,
                        '--source',str(work/'greedy_native_three3000_mouse.route'),'--seconds','1800',
                        '--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
    r=json.loads((work/f'{name}.json').read_text());results.append(r);print(json.dumps(r),flush=True)
    (work/'refresh_comparison.json').write_text(json.dumps(results,indent=2)+'\n')

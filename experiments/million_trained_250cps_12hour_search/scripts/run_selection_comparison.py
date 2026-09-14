"""Compare candidate selection against an older ruler, with a fixed opening."""
import json,subprocess,sys
from pathlib import Path
work=Path('/tmp/ccsr-trained-12h-20260914');here=Path(__file__).resolve().parent
common=dict(width=1200,inner=1500,pops=5000,workers=1,horizon=0,anchor=4,macro=1,
            order=1,prune=.94,heap=100000,nodes=1000000,compact=1,harvest=64,expansions=3000)
common.update({'future-mask':32768,'canonical-partials':1,'quantity-children':4,'age-bound':1,
               'start-prefix':4,'seed-prefixes':0,'persistent-workers':1,'stage-balance':1,
               'hand-dominance':1,'rollout-weight':.5,'hint-slack':1,'target-rollout':1,
               'retain-closed':1,'harvest-strategy':1,'harvest-slack':4,'report-generated':1})
results=[]
for keep in (0,80,160):
    name=f'selection_old_ruler_{keep}';options=dict(common,**{'rollout-keep':keep,'rollout-raw':keep//4})
    with (work/f'{name}.log').open('w') as log:
        subprocess.run([sys.executable,str(here/'run_native_beam.py'),name,'--source',str(work/'native_local_cool.route'),
                        '--seconds','300','--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((work/f'{name}.json').read_text());results.append(result);print(json.dumps(result),flush=True)
    (work/'selection_comparison.json').write_text(json.dumps(results,indent=2)+'\n')

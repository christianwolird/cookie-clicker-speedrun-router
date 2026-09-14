"""Compare incumbent-guided queue ordering, pruning and local breadth."""
import argparse,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--wait-for');args=p.parse_args()
work=Path('/tmp/ccsr-trained-12h-20260914');root=Path(__file__).resolve().parent
if args.wait_for:
    while not (work/args.wait_for).exists():time.sleep(15)
common=dict(width=1200,inner=1500,pops=5000,workers=2,horizon=0,anchor=4,macro=1,order=1,prune=.94,
            heap=500000,nodes=5000000,compact=1,harvest=128)
common.update({'future-mask':32768,'canonical-partials':1,'quantity-children':4,'persistent-workers':1,
               'stage-balance':1,'hand-dominance':1,'rollout-weight':.5,'hint-slack':1,
               'target-rollout':1,'report-generated':1,'harvest-strategy':1,'harvest-slack':4})
variants=[('baseline',{}),('prune090',dict(prune=.90)),('prune098',dict(prune=.98)),
          ('order097',dict(order=.97)),('rollout025',{'rollout-weight':.25}),
          ('rollout075',{'rollout-weight':.75}),('targets_only',{'target-rollout':2}),
          ('guide64',{'guide-width':64}),('early_global',{'stage-balance':0,'order':.99}),
          ('very_wide',dict(width=5000,inner=5000,pops=20000)),
          ('unit_only',{'quantity-children':1}),('bridge_jumps',{'quantity-children':5})]
results=[]
for label,extra in variants:
    name='param_guided_'+label;options=dict(common,**extra)
    with (work/f'{name}.log').open('w') as log:
        subprocess.run([sys.executable,str(root/'run_native_beam.py'),name,'--source',str(work/'session_best.route'),
                        '--seconds','600','--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((work/f'{name}.json').read_text());results.append(result);print(json.dumps(result),flush=True)
    (work/'parameter_b.json').write_text(json.dumps(results,indent=2)+'\n')

"""From-root beam comparisons without ruler-suffix completion."""
import argparse,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--wait-for');args=p.parse_args()
work=Path('/tmp/ccsr-trained-12h-20260914');root=Path(__file__).resolve().parent
if args.wait_for:
    while not (work/args.wait_for).exists():time.sleep(15)
common=dict(workers=2,horizon=0,anchor=4,macro=1,order=1,prune=.94,heap=400000,nodes=4000000,compact=1,
            harvest=192,rollout=0)
common.update({'future-mask':32768,'canonical-partials':1,'quantity-children':4,'persistent-workers':1,
               'stage-balance':1,'hand-dominance':1,'seed-prefixes':0,'harvest-slack':12,'harvest-strategy':1,'report-generated':1})
variants=[('narrow',dict(width=400,inner=800,pops=2000)),
          ('medium',dict(width=1200,inner=1500,pops=5000)),
          ('wide',dict(width=2500,inner=2000,pops=10000)),
          ('future',dict(width=1200,inner=1500,pops=5000,**{'future-inventory':.1})),
          ('raw',dict(width=1200,inner=1500,pops=5000,**{'future-mask':0})),
          ('diverse',dict(width=1200,inner=1500,pops=5000,**{'queue-diversity':2,'result-diversity':2}))]
results=[]
for label,extra in variants:
    name='param_root_'+label;options=dict(common,**extra)
    with (work/f'{name}.log').open('w') as log:
        subprocess.run([sys.executable,str(root/'run_native_beam.py'),name,'--source',str(work/'session_best.route'),
                        '--seconds','900','--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((work/f'{name}.json').read_text());results.append(result);print(json.dumps(result),flush=True)
    (work/'parameter_a.json').write_text(json.dumps(results,indent=2)+'\n')

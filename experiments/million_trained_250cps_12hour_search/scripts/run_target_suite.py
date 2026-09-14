"""Sequential target-inventory rollout trials, with frozen ruler snapshots."""
import json,subprocess,sys
from pathlib import Path
work=Path('/tmp/ccsr-trained-12h-20260914');root=Path(__file__).resolve().parent
for mode in (2,1):
    name=f'native_target_rollout_{mode}'
    options=dict(width=400,inner=800,pops=2000,workers=2,horizon=0,anchor=4,macro=1,
                 order=1,prune=.94,heap=200000,nodes=2000000,compact=1,harvest=192)
    options.update({'future-mask':32768,'canonical-partials':1,'quantity-children':1,
                    'persistent-workers':1,'stage-balance':1,'rollout-weight':.5,
                    'hint-slack':1,'hand-dominance':1,'target-rollout':mode})
    with (work/f'{name}.log').open('w') as log:
        subprocess.run([sys.executable,str(root/'run_native_beam.py'),name,'--source',str(work/'session_best.route'),
                        '--seconds','900','--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
    print(json.dumps(json.loads((work/f'{name}.json').read_text())),flush=True)

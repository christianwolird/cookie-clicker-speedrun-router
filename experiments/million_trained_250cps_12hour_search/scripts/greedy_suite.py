"""Cheap complete-route probes of native score settings."""
from pathlib import Path
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3];work=Path('/tmp/ccsr-trained-12h-20260914')
variants=[(f'lookahead{int(w*100)}',dict(two_step_pool=1000,two_step_weight=w)) for w in (0,.25,.5,.75,1)]
variants += [(f'lookahead100_bonus{int(b*100)}',dict(two_step_pool=1000,two_step_weight=1,upgrade_bonus=b)) for b in (.05,.1,.2)]
common=dict(native_backend=True,canonical_full_core=True,early_stop=False,all_evaluated=True,native_anchor_all=True,upgrade_macros=True)
for label,extra in variants:
    name='greedy_native_'+label;options=dict(common,**extra)
    cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_search.py'),name,'--greedy','--horizon','0','--width','80','--inner-width','200','--queue','1000','--ruler',str(work/'native_local_cool.route'),'--options-json',json.dumps(options)]
    with (work/f'{name}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
    if r.returncode:raise SystemExit(r.returncode)
    print((work/f'{name}.json').read_text(),flush=True)

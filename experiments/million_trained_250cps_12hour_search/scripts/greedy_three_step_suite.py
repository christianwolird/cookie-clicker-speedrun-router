"""Cheap complete-route probes of native score settings."""
from pathlib import Path
import json
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[3];work=Path('/tmp/ccsr-trained-12h-20260914')
variants=[('three500',dict(three_step=True,two_step_pool=500,two_step_weight=1,lookahead_branches=4)),('three500_mouse',dict(three_step=True,two_step_pool=500,two_step_weight=1,lookahead_branches=4,future_upgrade_mask=32768)),('three3000_mouse',dict(three_step=True,two_step_pool=3000,two_step_weight=1,lookahead_branches=4,future_upgrade_mask=32768)),('three3000_mouse_half',dict(three_step=True,two_step_pool=3000,two_step_weight=.5,lookahead_branches=4,future_upgrade_mask=32768))]
common=dict(native_backend=True,canonical_full_core=True,early_stop=False,all_evaluated=True,native_anchor_all=4,upgrade_macros=True)
for label,extra in variants:
    name='greedy_native_'+label;options=dict(common,**extra)
    cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_search.py'),name,'--greedy','--horizon','0','--width','80','--inner-width','200','--queue','1000','--ruler',str(work/'native_local_cool.route'),'--options-json',json.dumps(options)]
    with (work/f'{name}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
    if r.returncode:raise SystemExit(r.returncode)
    print((work/f'{name}.json').read_text(),flush=True)

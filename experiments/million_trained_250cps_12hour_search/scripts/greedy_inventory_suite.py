"""Independent greedy probes of the future-building score."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[3];work=Path('/tmp/ccsr-trained-12h-20260914')
for counts in ((0,5,5,2,0),(10,10,10,3,0),(20,20,15,5,0)):
    for mask in (0,32768):
        name=f'greedy_inventory_{counts[1]}_{mask}'
        options=dict(native_backend=True,canonical_full_core=True,canonical_partial=True,quantity_children=1,
                     early_stop=False,all_evaluated=True,native_anchor_all=4,upgrade_macros=True,
                     future_counts=counts,future_upgrade_mask=mask)
        cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_search.py'),name,'--greedy',
             '--horizon','0','--width','80','--inner-width','200','--queue','1000',
             '--ruler',str(work/'session_best.route'),'--options-json',json.dumps(options)]
        with (work/f'{name}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT,check=True)
        print((work/f'{name}.json').read_text(),flush=True)

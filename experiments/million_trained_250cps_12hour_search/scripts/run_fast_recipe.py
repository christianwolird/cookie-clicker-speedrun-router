"""Reproduce a strong trained-250 route from greedy choices and fixed refinement.

The existing route passed to run_search is only a reported comparison for a
greedy run; its purchases are never supplied to the greedy generator.
"""
import json,subprocess,sys,time
from pathlib import Path
from experiment_paths import ROOT,WORK
work=WORK;work.mkdir(parents=True,exist_ok=True);here=Path(__file__).resolve().parent
options=dict(native_backend=True,canonical_full_core=True,early_stop=False,all_evaluated=True,
             native_anchor_all=4,upgrade_macros=True,future_upgrade_mask=32768,three_step=True,
             two_step_pool=3000,two_step_weight=1,lookahead_branches=4)
start=time.monotonic()
with (work/'recipe_greedy.log').open('w') as log:
    subprocess.run([sys.executable,str(here/'run_search.py'),'recipe_greedy','--greedy','--horizon','0',
                    '--width','80','--inner-width','200','--queue','1000',
                    '--ruler',str(ROOT/'routes/million-250cps/generated_greedy.route'),
                    '--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
with (work/'recipe_refined.log').open('w') as log:
    subprocess.run([sys.executable,str(here/'run_native_local.py'),'recipe_refined','--source',str(work/'recipe_greedy.route'),
                    '--seconds','60','--trials','100000','--seed','945','--width','4','--tmax','.4',
                    '--tmin','.001','--cycle','20000','--blocks','--cache-size','100000'],stdout=log,stderr=subprocess.STDOUT,check=True)
result=dict(elapsed=time.monotonic()-start,greedy=json.loads((work/'recipe_greedy.json').read_text()),
            refined=json.loads((work/'recipe_refined.json').read_text()))
(work/'fast_recipe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

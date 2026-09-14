"""Reproduce the 198.140717-second incumbent without a supplied strategy."""
import json
from pathlib import Path
import subprocess
import sys
import time
from experiment_paths import WORK

work=WORK;work.mkdir(parents=True,exist_ok=True);here=Path(__file__).resolve().parent
options={'pool':1200,'inner':1500,'pops':5000,'rollout-width':40,'rollout-inner':100,'rollout-pops':300,'mode':2}
start=time.monotonic()
with (work/'recipe_best_greedy.log').open('w') as log:
    subprocess.run([sys.executable,str(here/'run_native_policy.py'),'recipe_best_greedy',
                    '--seconds','900','--options-json',json.dumps(options)],stdout=log,stderr=subprocess.STDOUT,check=True)
with (work/'recipe_best_refined.log').open('w') as log:
    subprocess.run([sys.executable,str(here/'run_native_local.py'),'recipe_best_refined',
                    '--source',str(work/'recipe_best_greedy.route'),'--seconds','90','--trials','50000',
                    '--seed','17945','--width','4','--tmax','.4','--tmin','.001','--cycle','20000',
                    '--blocks','--cache-size','100000','--lock-upgrades'],stdout=log,stderr=subprocess.STDOUT,check=True)
result=dict(elapsed=time.monotonic()-start,greedy=json.loads((work/'recipe_best_greedy.json').read_text()),
            refined=json.loads((work/'recipe_best_refined.json').read_text()))
(work/'best_recipe.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

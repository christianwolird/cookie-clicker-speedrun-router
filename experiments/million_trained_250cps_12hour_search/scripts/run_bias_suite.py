"""Use search-energy biases to explore different route shapes at trained timing."""
import json
from pathlib import Path
import subprocess
import sys
import time
from experiment_paths import WORK

work=WORK;here=Path(__file__).resolve().parent
while not Path('/tmp/ccsr-trained-best-reproduction/best_recipe.json').exists():time.sleep(2)
variants=[('errand005',.05,0),('errand020',.2,0),('more_errands',-.05,0),
          ('action005',0,.05),('action020',0,.2),('more_actions',0,-.05),('combined',.1,.05)]
results=[]
for index,(label,errand_bias,action_bias) in enumerate(variants):
    name='shape_bias_'+label
    command=[sys.executable,str(here/'run_native_local.py'),name,'--source',str(work/'session_best.route'),
             '--extra-directory',str(work/'diverse_counts_archive_candidates'),'--seconds','300',
             '--width','4','--seed',str(24000+index),'--tmax','.8','--tmin','.001','--cycle','30000',
             '--blocks','--cache-size','100000','--restart-best','.25',
             '--errand-bias',str(errand_bias),'--action-bias',str(action_bias)]
    with (work/f'{name}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    row=json.loads((work/f'{name}.json').read_text());results.append(row);print(json.dumps(row),flush=True)
    (work/'shape_bias_results.json').write_text(json.dumps(results,indent=2)+'\n')

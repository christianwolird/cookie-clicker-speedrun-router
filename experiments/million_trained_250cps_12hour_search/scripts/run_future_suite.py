"""Compare prospective Plastic-mouse value using a frozen ruler."""
from pathlib import Path
import json,subprocess,sys,time,shutil
ROOT=Path(__file__).resolve().parents[3];work=Path('/tmp/ccsr-trained-12h-20260914')
ruler=work/'future_suite_ruler.route';shutil.copyfile(work/'native_local_cool.route',ruler)
common=dict(width=160,inner=400,pops=1000,workers=2,rollout=1,macro=1,anchor=4,horizon=0,heap=500000,nodes=5000000,harvest=96)
variants=[('mouse',{'future-mask':32768}),('mouse_half',{'future-mask':32768,'future-weight':.5}),('mouse_diverse',{'future-mask':32768,'result-diversity':3,'queue-diversity':3})]
for label,extra in variants:
    name='native_future_'+label;options=dict(common,**extra)
    print(json.dumps(dict(event='start_trial',name=name,time=time.time(),options=options)),flush=True)
    cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_native_beam.py'),name,'--source',str(ruler),'--seconds','900','--options-json',json.dumps(options)]
    with (work/f'{name}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
    print(json.dumps(dict(event='finish_trial',name=name,time=time.time(),returncode=r.returncode)),flush=True)
    if r.returncode:raise SystemExit(r.returncode)

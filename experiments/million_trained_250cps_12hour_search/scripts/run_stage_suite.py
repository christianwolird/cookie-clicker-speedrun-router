"""Factorial comparison after correcting stage starvation."""
from pathlib import Path
import subprocess,json,sys,time,shutil
ROOT=Path(__file__).resolve().parents[3];work=Path('/tmp/ccsr-trained-12h-20260914')
ruler=work/'stage_suite_ruler.route';shutil.copyfile(work/'native_local_cool.route',ruler)
variants=[('baseline',{}),('mouse',{'future-mask':32768}),('guided',{'guide-width':64}),('mouse_guided',{'future-mask':32768,'guide-width':64})]
common=dict(width=160,inner=400,pops=1000,horizon=0,workers=2,anchor=4,macro=1,order=1,heap=200000,nodes=2000000,compact=1,harvest=128)
common.update({'stage-balance':1,'rollout-weight':.5,'hint-slack':1})
for label,extra in variants:
    name='native_stage_'+label;options=dict(common,**extra)
    print(json.dumps(dict(event='start_trial',name=name,time=time.time(),options=options)),flush=True)
    cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_native_beam.py'),name,'--source',str(ruler),'--seconds','900','--options-json',json.dumps(options)]
    with (work/f'{name}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
    if r.returncode:raise SystemExit(r.returncode)
    print(json.dumps(dict(event='finish_trial',name=name,time=time.time(),result=json.loads((work/f'{name}.json').read_text()))),flush=True)

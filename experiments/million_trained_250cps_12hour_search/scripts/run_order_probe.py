from pathlib import Path
import subprocess,json,sys,time
ROOT=Path(__file__).resolve().parents[3];work=Path('/tmp/ccsr-trained-12h-20260914')
for scalar in (1.01,1,.99,.97):
    name=f'native_order_{scalar:.2f}'
    options=dict(width=80,inner=160,pops=500,horizon=0,workers=1,anchor=4,macro=1,order=scalar)
    options.update({'future-mask':32768,'guide-width':64,'rollout-weight':.5,'hint-slack':1,'harvest':64})
    cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_native_beam.py'),name,'--source',str(work/'native_local_cool.route'),'--seconds','120','--options-json',json.dumps(options)]
    print(json.dumps(dict(event='start_trial',name=name,time=time.time())),flush=True)
    with (work/f'{name}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
    if r.returncode:raise SystemExit(r.returncode)
    print((work/f'{name}.json').read_text(),flush=True)

"""Controlled compiled-search comparisons with frozen input and source snapshots."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3];WORK=Path('/tmp/ccsr-trained-12h-20260914')
p=argparse.ArgumentParser();p.add_argument('--prefix',default='native_suite2');p.add_argument('--seconds',type=float,default=900)
p.add_argument('--wait-for',default='native_rollout_probe.json');args=p.parse_args()
started=time.monotonic()
while args.wait_for and not (WORK/args.wait_for).exists():
    if time.monotonic()-started>1800:raise TimeoutError(args.wait_for)
    time.sleep(2)
source=WORK/f'{args.prefix}_ruler.route';source.write_text((WORK/'native_local_cool.route').read_text())
common=dict(width=160,inner=400,pops=1000,workers=4,rollout=1,macro=1,anchor=1,horizon=0,heap=500000,nodes=5000000)
variants=[('unbounded',common),
          ('lookahead',dict(common,**{'two-step-pool':1000,'two-step-weight':1})),
          ('rollout_rank',dict(common,**{'rollout-weight':.75,'hint-slack':.75})),
          ('combined',dict(common,**{'two-step-pool':1000,'two-step-weight':1,'rollout-weight':.75,'hint-slack':.75})),
          ('diverse',dict(common,anchor=0,reserve=12,**{'queue-diversity':3,'result-diversity':2,'two-step-pool':1000,'two-step-weight':1,'rollout-weight':.75,'hint-slack':.75})),
          ('wide',dict(common,width=400,inner=1000,pops=5000,**{'rollout-weight':.75,'hint-slack':.75}))]
for label,options in variants:
    name=f'{args.prefix}_{label}'
    print(json.dumps(dict(event='start_trial',name=name,time=time.time(),options=options)),flush=True)
    cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_native_beam.py'),name,'--source',str(source),'--seconds',str(args.seconds),'--options-json',json.dumps(options)]
    with (WORK/f'{name}.log').open('w') as log:r=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
    print(json.dumps(dict(event='finish_trial',name=name,time=time.time(),returncode=r.returncode)),flush=True)
    if r.returncode:raise SystemExit(r.returncode)

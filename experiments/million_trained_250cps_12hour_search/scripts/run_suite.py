"""Sequential trial scheduler; each child records its own replay-verified result."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
WORK=Path('/tmp/ccsr-trained-12h-20260914')

def main():
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=180);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--prefix',default='sweep1');args=p.parse_args()
    variants=['no_stop','bonus10','bonus20','diverse','reserved','balanced','balanced_bonus10']
    ruler=WORK/'local_v1.route'
    snapshot=WORK/f'{args.prefix}_ruler.route';snapshot.write_text(ruler.read_text())
    for variant in variants:
        name=f'{args.prefix}_{variant}'
        cmd=[sys.executable,str(ROOT/'experiments/million_trained_250cps_12hour_search/scripts/run_search.py'),name,
             '--variant',variant,'--seconds',str(args.seconds),'--workers',str(args.workers),
             '--ruler',str(snapshot)]
        print(json.dumps({'event':'start_trial','name':name,'time':time.time()}),flush=True)
        with (WORK/f'{name}.log').open('w') as log:
            result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,cwd=ROOT)
        print(json.dumps({'event':'finish_trial','name':name,'returncode':result.returncode,'time':time.time()}),flush=True)
        if result.returncode: raise SystemExit(result.returncode)

if __name__=='__main__':main()

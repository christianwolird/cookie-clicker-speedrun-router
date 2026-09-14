"""Refine half of the diverse-count archive using bounded, unique trials."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from experiment_paths import WORK

p=argparse.ArgumentParser();p.add_argument('--shard',type=int,choices=(0,1),required=True);args=p.parse_args()
work=WORK;here=Path(__file__).resolve().parent;manifest=work/'counts_archive_manifest.json'
while not manifest.exists():time.sleep(2)
seeds=json.loads(manifest.read_text());results=[]
for i,row in enumerate(seeds):
    if i%2!=args.shard:continue
    name=f'archive_counts_refined_{i:03d}'
    cmd=[sys.executable,str(here/'run_native_local.py'),name,'--source',row['path'],
         '--seconds','20','--width','4','--seed',str(14000+i),'--blocks','--cache-size','100000',
         '--tmax','.4' if args.shard else '.8','--tmin','.001','--cycle','20000']
    if args.shard:cmd.append('--lock-upgrades')
    with (work/f'{name}.log').open('w') as log:subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((work/f'{name}.json').read_text());results.append(result)
    print(json.dumps(dict(index=i,finish=result['finish'],elapsed=result['elapsed'])),flush=True)
    (work/f'archive_counts_refinement_{args.shard}.json').write_text(json.dumps(results,indent=2)+'\n')

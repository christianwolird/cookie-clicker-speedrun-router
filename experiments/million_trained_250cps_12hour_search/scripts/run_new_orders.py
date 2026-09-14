"""Refine upgrade orders discovered beyond the initial local seed sweep."""
import argparse,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--shard',type=int,required=True);p.add_argument('--shards',type=int,default=2)
p.add_argument('--seconds',type=int,default=30);p.add_argument('--wait-for')
p.add_argument('--prefix',default='new_cached_order');args=p.parse_args()
work=Path('/tmp/ccsr-trained-12h-20260914');root=Path(__file__).resolve().parent
if args.wait_for:
    while not (work/args.wait_for).exists():time.sleep(15)
rows=json.loads((work/'new_upgrade_orders.json').read_text());results=[]
for i,row in enumerate(rows):
    if i%args.shards!=args.shard:continue
    name=f'{args.prefix}_{i:03d}'
    command=[sys.executable,str(root/'run_native_local.py'),name,'--source',row['path'],
             '--seconds',str(args.seconds),'--seed',str(2001+i),'--width','4','--tmax','.4',
             '--tmin','.001','--cycle','20000','--lock-upgrades','--blocks','--cache-size','100000']
    with (work/f'{name}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((work/f'{name}.json').read_text());result['initial']=row['finish'];results.append(result)
    print(json.dumps(result),flush=True)
    (work/f'{args.prefix}_suite_{args.shard}.json').write_text(json.dumps(results,indent=2)+'\n')

"""Give each alternative upgrade order a fixed refinement budget."""
import argparse,json,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--shard',type=int,required=True);p.add_argument('--shards',type=int,default=2)
p.add_argument('--seconds',type=int,default=60);p.add_argument('--wait-for');args=p.parse_args()
work=Path('/tmp/ccsr-trained-12h-20260914');root=Path(__file__).resolve().parent
if args.wait_for:
    while not (work/args.wait_for).exists():time.sleep(15)
rows=json.loads((work/'upgrade_order_seeds.json').read_text());results=[]
for i,row in enumerate(rows):
    if i%args.shards!=args.shard:continue
    name=f'locked_order_{i:03d}'
    command=[sys.executable,str(root/'run_native_local.py'),name,'--source',row['path'],
             '--seconds',str(args.seconds),'--seed',str(1001+i),'--width','4','--tmax','1',
             '--tmin','.002','--cycle','30000','--lock-upgrades','--blocks']
    with (work/f'{name}.log').open('w') as log:subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,check=True)
    result=json.loads((work/f'{name}.json').read_text());result['initial']=row['finish'];results.append(result)
    print(json.dumps(result),flush=True)
    (work/f'locked_suite_{args.shard}.json').write_text(json.dumps(results,indent=2)+'\n')

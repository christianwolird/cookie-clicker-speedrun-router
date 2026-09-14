"""Verify identical fixed-trial annealing with and without exact memoization."""
import json,resource,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route
from native_bridge import pack_actions
work=Path('/tmp/ccsr-trained-12h-20260914');rows=[]
for locked in (0,1):
    source=work/('upgrade_order_seeds/upgrade_order_seed_008.route' if locked else 'greedy_native_three3000_mouse.route')
    base=load_route(source);seed=work/f'cache_benchmark_{locked}.seed'
    seed.write_text(str(len(base.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(map(str,pack_actions(e))) for e in base.errands)+'\n')
    previous=None
    for limit in (0,100000):
        command=[str(work/'native_anneal'),str(seed),'60','945','4','16','.4','.001','20000','0','0','0','1','0','0',str(locked),'.75',str(limit),'100000']
        usage=resource.getrusage(resource.RUSAGE_CHILDREN);before=usage.ru_utime+usage.ru_stime
        result=subprocess.run(command,capture_output=True,text=True,check=True)
        usage=resource.getrusage(resource.RUSAGE_CHILDREN);cpu=usage.ru_utime+usage.ru_stime-before
        data=[json.loads(line) for line in result.stdout.splitlines()];last=data[-1];assert last['tried']==100000
        signature=[(r['finish'],r['route']) for r in data if 'route' in r]
        signature.append({k:last[k] for k in ('tried','accepted','improvements')})
        if previous is not None:assert signature==previous
        previous=signature
        row=dict(locked=locked,cache=limit,cpu=cpu,**{k:v for k,v in last.items() if k not in ('route','event')});rows.append(row);print(json.dumps(row),flush=True)
(work/'benchmark_partition_cache.json').write_text(json.dumps(rows,indent=2)+'\n')

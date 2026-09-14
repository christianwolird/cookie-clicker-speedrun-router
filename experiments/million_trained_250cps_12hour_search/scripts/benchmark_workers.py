"""Compare fixed expansion counts, including exact search-output checks."""
import json,resource,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,execute_route
from native_bridge import pack_actions,unpack_actions
from dataclasses import replace
work=Path('/tmp/ccsr-trained-12h-20260914');base=load_route(work/'session_best.route');seed=work/'pool_benchmark.seed'
seed.write_text(str(len(base.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(str(c) for c in pack_actions(e)) for e in base.errands)+'\n')
rows=[]
for pops in (100,1000):
    previous=None
    for pool in (0,1):
        command=[str(work/'native_beam'),'--seed',str(seed),'--seconds','120','--expansions','1000','--workers','4','--width','80','--inner','160','--pops',str(pops),'--horizon','0','--order','1','--stage-balance','1','--quantity-children','1','--canonical-partials','1','--future-mask','32768','--persistent-workers',str(pool)]
        usage=resource.getrusage(resource.RUSAGE_CHILDREN);before=usage.ru_utime+usage.ru_stime
        output=subprocess.run(command,check=True,capture_output=True,text=True)
        usage=resource.getrusage(resource.RUSAGE_CHILDREN);cpu=usage.ru_utime+usage.ru_stime-before
        data=[json.loads(line) for line in output.stdout.splitlines()];last=data[-1]
        assert last['termination']=='expansion_limit',last
        signature=[(row['finish'],row['route']) for row in data if 'route' in row]
        signature.append({k:last[k] for k in ('expanded','generated','nodes','expanded_by_baked')})
        if previous is not None:assert signature==previous,(pops,last)
        previous=signature
        for row in data:
            if 'route' in row:
                plan=replace(base,errands=tuple(unpack_actions(e) for e in row['route']))
                assert abs(execute_route(plan).final_gamestate.age-row['finish'])<1e-7
        row=dict(pops=pops,persistent=pool,cpu=cpu,wall=last['elapsed'],expanded=last['expanded'],generated=last['generated'],finish=last['finish']);rows.append(row);print(json.dumps(row),flush=True)
(work/'benchmark_workers.json').write_text(json.dumps(rows,indent=2)+'\n')

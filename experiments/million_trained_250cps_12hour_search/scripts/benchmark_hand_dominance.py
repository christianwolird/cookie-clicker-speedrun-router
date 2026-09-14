"""Compare search effort with exact handmade-cookie Pareto dominance."""
import json,resource,subprocess,sys
from pathlib import Path
from dataclasses import replace
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,execute_route
from native_bridge import pack_actions,unpack_actions
work=Path('/tmp/ccsr-trained-12h-20260914');base=load_route(work/'session_best.route');seed=work/'hand_benchmark.seed'
seed.write_text(str(len(base.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(str(c) for c in pack_actions(e)) for e in base.errands)+'\n')
rows=[]
for dominance in (0,1):
    command=[str(work/'native_beam'),'--seed',str(seed),'--seconds','240','--expansions','40000',
             '--workers','2','--width','160','--inner','400','--pops','1000','--horizon','0',
             '--order','1','--stage-balance','1','--quantity-children','1','--canonical-partials','1',
             '--future-mask','32768','--persistent-workers','1','--hand-dominance',str(dominance),
             '--rollout-weight','.5','--hint-slack','1','--heap','200000','--nodes','2000000','--compact','1']
    usage=resource.getrusage(resource.RUSAGE_CHILDREN);before=usage.ru_utime+usage.ru_stime
    output=subprocess.run(command,check=True,capture_output=True,text=True)
    usage=resource.getrusage(resource.RUSAGE_CHILDREN);cpu=usage.ru_utime+usage.ru_stime-before
    data=[json.loads(line) for line in output.stdout.splitlines()];last=data[-1]
    for row in data:
        if 'route' in row:
            plan=replace(base,errands=tuple(unpack_actions(e) for e in row['route']))
            assert abs(execute_route(plan).final_gamestate.age-row['finish'])<1e-7
    row=dict(dominance=dominance,cpu=cpu,**{k:v for k,v in last.items() if k!='route'});rows.append(row);print(json.dumps(row),flush=True)
(work/'benchmark_hand_dominance.json').write_text(json.dumps(rows,indent=2)+'\n')

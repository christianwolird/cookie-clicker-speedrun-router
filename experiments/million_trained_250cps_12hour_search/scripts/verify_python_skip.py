import importlib.util,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from ccsr.errands.generator import generate_neighbors
work=Path('/tmp/ccsr-trained-12h-20260914')
spec=importlib.util.spec_from_file_location('ccsr.errands._before_skip',work/'python_generator_before_skip.py');before=importlib.util.module_from_spec(spec);spec.loader.exec_module(before)
samples=[]
for name in ('session_best.route','incumbent_start.route','greedy_native_three3000_mouse.route'):
    plan=load_route(work/name);s=initial_gamestate(plan);samples.append(s)
    for a in plan.errands:s,_=apply_errand(s,a);samples.append(s)
def signature(n):
    s=n.gamestate
    return (n.errand,s.age,s.bank,s.lifetime_cookies,s.handmade_cookies,tuple(s.building_counts.items()),frozenset(s.purchased_upgrades),n.score)
cpu=[0.,0.];returned=0
for i,state in enumerate(samples):
    output=[]
    for j,function in enumerate((before.generate_neighbors,generate_neighbors)):
        start=time.process_time();ns=function(state,1000000,width=20,search_width=40,queue_expansions=100,price_horizon_multiplier=16,max_errand_actions=12);cpu[j]+=time.process_time()-start
        output.append(tuple(signature(n) for n in ns))
    assert output[0]==output[1],i
    returned+=len(output[0])
result=dict(states=len(samples),returned=returned,before_cpu=cpu[0],after_cpu=cpu[1],speedup=cpu[0]/cpu[1]);(work/'verify_python_skip.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

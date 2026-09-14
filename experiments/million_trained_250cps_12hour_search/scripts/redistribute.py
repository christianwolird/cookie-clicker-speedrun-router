"""Systematic multi-copy redistribution with native DP and stock verification."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,execute_route,write_route,RouteAction
from native_bridge import partition_actions

work=Path('/tmp/ccsr-trained-12h-20260914');base=load_route(work/'native_local_cool.route');best=base
initial=best_age=execute_route(best).final_gamestate.age;start=time.monotonic();tried=0;seen=set();improvements=[]
def candidates(actions):
    for i,a in enumerate(actions):
        if a.operation!='buy':continue
        for j,b in enumerate(actions):
            if i==j or b.operation!='buy' or b.item!=a.item:continue
            for amount in range(1,a.quantity+1):
                out=[]
                for k,c in enumerate(actions):
                    q=c.quantity-amount if k==i else c.quantity+amount if k==j else c.quantity
                    if c.operation=='buy':
                        while q:part=min(10,q);out.append(replace(c,quantity=part));q-=part
                    else:out.append(c)
                yield tuple(out)
        for amount in range(1,a.quantity):
            for j in range(len(actions)+1):
                out=[]
                for k in range(len(actions)+1):
                    if k==j:out.append(replace(a,quantity=amount))
                    if k<len(actions):out.append(replace(a,quantity=a.quantity-amount) if k==i else actions[k])
                yield tuple(out)
    buys=[i for i,a in enumerate(actions) if a.operation=='buy']
    for ix,i in enumerate(buys):
        for j in buys[ix+1:]:
            for di in (-2,-1,1,2):
                for dj in (-2,-1,1,2):
                    qi=actions[i].quantity+di;qj=actions[j].quantity+dj
                    if not(1<=qi<=10 and 1<=qj<=10):continue
                    out=list(actions);out[i]=replace(out[i],quantity=qi);out[j]=replace(out[j],quantity=qj)
                    yield tuple(out)
for iteration in range(20):
    improved=None;candidate_age=best_age
    for actions in candidates(best.actions):
        if actions in seen:continue
        seen.add(actions);tried+=1
        errands,score=partition_actions(actions,width=4,max_size=16)
        if score<candidate_age-1e-9:
            candidate=replace(base,errands=errands)
            verified=execute_route(candidate).final_gamestate.age
            assert abs(verified-score)<1e-7
            improved=candidate;candidate_age=verified
    if improved is None:break
    best=improved;best_age=candidate_age
    row=dict(iteration=iteration+1,finish=best_age,elapsed=time.monotonic()-start,tried=tried);improvements.append(row);print(json.dumps(row),flush=True)
plan=replace(best,name='redistributed',algorithm='experimental_native_redistribution',price_horizon_multiplier=None,errand_queue_depth=None,
             beam_width=None,errand_search_width=None,ruler_scale=None,ruler_route=None,beam_max_expansions=None)
write_route(work/'redistributed.route',plan,overwrite=True)
result=dict(initial=initial,finish=best_age,elapsed=time.monotonic()-start,tried=tried,improvements=improvements)
(work/'redistributed.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(event='complete',**result)),flush=True)

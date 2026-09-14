"""Compare cached evaluation with stock simulation on valid and invalid candidates."""
import json
from pathlib import Path
import random
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from ccsr.errands.generator import initial_errands,added_purchase_errands,_evaluate,generate_neighbors
from generator_variants import canonical_full_core
from fast_evaluator import Evaluator

work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'local_v1.route')
state=initial_gamestate(plan);states=[];rng=random.Random(61)
for actions in plan.errands:
    states.append(state);state,_=apply_errand(state,actions)
    waiting=state.copy();delay=rng.uniform(0,12)
    waiting.age+=delay;waiting.bank+=waiting.cps()*delay;waiting.lifetime_cookies+=waiting.cps()*delay
    waiting.handmade_cookies+=waiting.hand_cps()*delay;states.append(waiting)
started=time.monotonic();tried=valid=0;fast_seconds=stock_seconds=0
for i,state in enumerate(states):
    fast=Evaluator(state,plan.target,16)
    parents=[n.errand for n in generate_neighbors(state,plan.target,width=30,search_width=60,queue_expansions=100,price_horizon_multiplier=16)]
    candidates=list(initial_errands(state))
    if not parents:parents=candidates
    for _ in range(60):
        parent=rng.choice(parents)
        children=list(added_purchase_errands(state,parent));rng.shuffle(children)
        candidates+=children[:50]
    candidates += [canonical_full_core(state,e) for e in candidates]
    for errand in candidates:
        before=time.monotonic();expected=_evaluate(state,plan.target,errand,16);stock_seconds+=time.monotonic()-before
        before=time.monotonic();actual=fast(errand);fast_seconds+=time.monotonic()-before
        tried+=1
        assert (expected is None)==(actual is None),(i,errand,expected,actual)
        if expected is None:continue
        valid+=1
        assert expected.purchases==actual.purchases,(i,errand,expected.purchases,actual.purchases)
        assert expected.score==actual.score
        assert expected.acquisition_time==actual.acquisition_time
        a,b=expected.gamestate,actual.gamestate
        for field in ('age','bank','lifetime_cookies','handmade_cookies','building_counts','purchased_upgrades'):
            assert getattr(a,field)==getattr(b,field),(i,field,getattr(a,field),getattr(b,field))
    print(json.dumps(dict(event='progress',state=i+1,tried=tried,valid=valid,elapsed=time.monotonic()-started)),flush=True)
result=dict(states=len(states),tried=tried,valid=valid,stock_seconds=stock_seconds,fast_seconds=fast_seconds,elapsed=time.monotonic()-started)
(work/'verify_fast_evaluator.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(event='complete',**result)),flush=True)

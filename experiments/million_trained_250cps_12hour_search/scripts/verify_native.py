"""Validate the native model against original Python game/shop execution."""
from dataclasses import replace
import ctypes as C
import json
from pathlib import Path
import random
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from ccsr.errands.generator import generate_neighbors,added_purchase_errands,_evaluate
from generator_variants import canonical_full_core
from native_bridge import evaluate,pack_state,LIB

work=Path('/tmp/ccsr-trained-12h-20260914');rng=random.Random(73);started=time.monotonic()
plan=load_route(work/'local_v1.route');state=initial_gamestate(plan);states=[]
for actions in plan.errands:
    states.append(state);state,_=apply_errand(state,actions)
    waiting=state.copy();delay=rng.uniform(0,10)
    waiting.age+=delay;waiting.bank+=waiting.cps()*delay;waiting.lifetime_cookies+=waiting.cps()*delay
    waiting.handmade_cookies+=waiting.hand_cps()*delay;states.append(waiting)
tried=valid=0;max_error=0
for i,state in enumerate(states):
    packed=pack_state(state);rr=(C.c_double*2)();LIB.native_rates(C.byref(packed),rr)
    assert abs(rr[0]-state.automatic_cps())<1e-8,(rr[0],state.automatic_cps())
    assert abs(rr[1]-state.hand_cps())<1e-8,(rr[1],state.hand_cps())
    parents=[n.errand for n in generate_neighbors(state,plan.target,width=30,search_width=60,queue_expansions=100,price_horizon_multiplier=16)]
    candidates=list(parents)
    if not parents:continue
    for _ in range(35):
        children=list(added_purchase_errands(state,rng.choice(parents)));rng.shuffle(children);candidates+=children[:50]
    candidates += [canonical_full_core(state,e) for e in candidates]
    for errand in candidates:
        actions=errand.actions(state)
        # Catalog entries priced above the goal are intentionally unrepresented.
        try:actual=evaluate(state,actions)
        except ValueError:continue
        expected=_evaluate(state,plan.target,errand,16);tried+=1
        assert (expected is None)==(actual is None),(i,errand,expected,actual)
        if expected is None:continue
        valid+=1;a=expected.gamestate;b=actual
        assert a.building_counts==b.building_counts and a.purchased_upgrades==b.purchased_upgrades
        for field in ('age','bank','lifetime_cookies','handmade_cookies'):
            error=abs(getattr(a,field)-getattr(b,field));max_error=max(max_error,error)
            assert error<1e-7,(i,field,error)
    print(json.dumps(dict(event='progress',state=i+1,tried=tried,valid=valid,max_error=max_error,elapsed=time.monotonic()-started)),flush=True)
result=dict(states=len(states),tried=tried,valid=valid,max_error=max_error,elapsed=time.monotonic()-started)
(work/'verify_native.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(event='complete',**result)),flush=True)

"""Cross-check native evaluation on independently sampled feasible game states."""
import ctypes as C
import json
from pathlib import Path
import random
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.config import load_route_profile,create_initial_gamestate
from ccsr.routes import RouteAction
from ccsr.routes.replay import apply_errand
from ccsr.errands.generator import _upgrade_errand
from native_bridge import evaluate,pack_state,LIB,BUILDINGS,UPGRADES

rng=random.Random(4501);work=Path('/tmp/ccsr-trained-12h-20260914');profile=load_route_profile('million-250cps')
state=create_initial_gamestate(profile);checked=valid=states=0;max_error=0;seen_upgrades=set();start=time.monotonic()
for iteration in range(3000):
    if iteration%12==0 or state.lifetime_cookies>950000:state=create_initial_gamestate(profile)
    packed=pack_state(state);rr=(C.c_double*2)();LIB.native_rates(C.byref(packed),rr)
    assert abs(rr[0]-state.automatic_cps())<1e-8
    assert abs(rr[1]-state.hand_cps())<1e-8
    candidates=[(RouteAction('buy',rng.choice(BUILDINGS),rng.randint(1,10)),) for _ in range(12)]
    choices=[n for n in UPGRADES if n not in state.purchased_upgrades]
    for name in rng.sample(choices,min(8,len(choices))):candidates.append(_upgrade_errand(state,name).actions(state))
    children=[]
    for actions in candidates:
        expected=None
        try:
            child,_=apply_errand(state,actions)
            if child.lifetime_cookies<1_000_000:expected=child
        except (KeyError,ValueError):pass
        actual=evaluate(state,actions,horizon=0);checked+=1
        assert (expected is None)==(actual is None),(actions,state,expected,actual)
        if expected is None:continue
        valid+=1;children.append((actions,expected))
        for field in ('age','bank','lifetime_cookies','handmade_cookies'):
            error=abs(getattr(expected,field)-getattr(actual,field));max_error=max(max_error,error)
            assert error<1e-7,(field,actions,error)
        assert expected.building_counts==actual.building_counts and expected.purchased_upgrades==actual.purchased_upgrades
        seen_upgrades.update(expected.purchased_upgrades)
    if children:
        upgrades=[c for c in children if any(a.operation=='upgrade' for a in c[0])]
        _,state=rng.choice(upgrades if upgrades and rng.random()<.6 else children)
    else:state=create_initial_gamestate(profile)
    states+=1
result=dict(states=states,candidates=checked,valid=valid,max_error=max_error,seen_upgrades=sorted(seen_upgrades),elapsed=time.monotonic()-start)
(work/'verify_native_random.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)

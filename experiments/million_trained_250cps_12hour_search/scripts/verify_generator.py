"""Property checks for the experimental exact filters and x10 normalization."""
from dataclasses import replace
import json
from pathlib import Path
import random
import sys
import time
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from ccsr.errands.generator import generate_neighbors as original,initial_errands,added_purchase_errands,_evaluate
from generator_variants import Options,generate_neighbors,canonical_full_core

work=Path('/tmp/ccsr-trained-12h-20260914');rng=random.Random(17)
plan=load_route(work/'local_v1.route');states=[];state=initial_gamestate(plan)
for actions in plan.errands:
    states.append(state);state,_=apply_errand(state,actions)
start=time.monotonic();equivalent=changed=valid=tried=0
for i,state in enumerate(states):
    expected=original(state,plan.target,width=20,search_width=40,queue_expansions=100,price_horizon_multiplier=16)
    actual=generate_neighbors(state,plan.target,width=20,search_width=40,queue_expansions=100,price_horizon_multiplier=16,options=Options())
    assert [n.errand for n in expected]==[n.errand for n in actual],i
    assert [n.gamestate.age for n in expected]==[n.gamestate.age for n in actual],i
    equivalent+=1
    parents=[n.errand for n in expected]
    for _ in range(35):
        parent=rng.choice(parents)
        candidates=list(added_purchase_errands(state,parent));rng.shuffle(candidates)
        for errand in candidates[:70]:
            tried+=1
            raw=_evaluate(state,plan.target,errand,16)
            if raw is None:continue
            valid+=1;normalized=canonical_full_core(state,errand)
            canonical=_evaluate(state,plan.target,normalized,16)
            assert canonical is not None,(i,errand,normalized)
            a,b=raw.gamestate,canonical.gamestate
            assert a.building_counts==b.building_counts
            assert a.purchased_upgrades==b.purchased_upgrades
            for field in ('age','bank','lifetime_cookies','handmade_cookies'):
                assert abs(getattr(a,field)-getattr(b,field))<1e-8,(field,i,errand,normalized)
            assert abs(a.cps()-b.cps())<1e-8
            changed+=normalized!=errand
            if len(parents)<300:parents.append(errand)
    print(json.dumps(dict(event='progress',state=i+1,equivalent=equivalent,tried=tried,valid=valid,normalized=changed,elapsed=time.monotonic()-start)),flush=True)
result=dict(equivalent_states=equivalent,candidates=tried,valid=valid,changed=changed,elapsed=time.monotonic()-start)
(work/'verify_generator.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(dict(event='complete',**result)),flush=True)

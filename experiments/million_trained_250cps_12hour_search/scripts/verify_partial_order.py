"""Exhaustive small-permutation checks against authoritative Python replay."""
import itertools,json,random,sys,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.config import load_route_profile,create_initial_gamestate
from ccsr.routes import RouteAction,load_route,initial_gamestate
from ccsr.routes.replay import apply_errand
from native_bridge import BUILDINGS,UPGRADES,canonical_actions,evaluate
rng=random.Random(901);work=Path('/tmp/ccsr-trained-12h-20260914');profile=load_route_profile('million-250cps')
plan=load_route(work/'native_local_cool.route');s=initial_gamestate(plan);samples=[s]
for a in plan.errands:s,_=apply_errand(s,a);samples.append(s)
checked=valid=rescued=multiple=positive=0;start=time.monotonic();s=samples[0]
def stock(s,a):
    try:
        c,_=apply_errand(s,a)
        return c if c.lifetime_cookies<1000000 else None
    except (ValueError,KeyError):return None
for case in range(5000):
    if case%8==0:s=rng.choice(samples).copy()
    if s.lifetime_cookies>950000:s=samples[0].copy()
    if rng.random()<.3:
        s=s.copy();dt=rng.random()*.5;produced=s.cps()*dt
        s.age+=dt;s.bank+=produced;s.lifetime_cookies+=produced;s.handmade_cookies+=s.hand_cps()*dt
    positive+=s.bank>0
    types=rng.sample(BUILDINGS,rng.randint(1,4))
    actions=[RouteAction('buy',b,rng.randint(1,9)) for b in types]
    counts=dict(s.building_counts)
    if len(actions)<5 and rng.random()<.5:
        b=rng.choice(BUILDINGS);actions.append(RouteAction('buy',b,10));counts[b]+=10
    ready=[name for name in UPGRADES if name not in s.purchased_upgrades and all(counts[b]>=q for b,q in s.upgrade_catalog[name].requirements)]
    if len(actions)<5 and ready and rng.random()<.7:actions.append(RouteAction('upgrade',rng.choice(ready)))
    rng.shuffle(actions);a=tuple(actions);normal=canonical_actions(s,a)
    assert Counter(a)==Counter(normal)
    expected=stock(s,normal);native=evaluate(s,normal,horizon=0)
    assert (expected is None)==(native is None)
    if expected is not None:
        for field in ('age','bank','lifetime_cookies','handmade_cookies'):
            assert abs(getattr(expected,field)-getattr(native,field))<1e-7
    found=0
    for permutation in set(itertools.permutations(a)):
        child=stock(s,permutation);checked+=1
        if child is None:continue
        valid+=1;found+=1
        assert expected is not None,(case,a,normal,permutation,s)
        for field in ('age','bank','lifetime_cookies','handmade_cookies'):
            assert abs(getattr(child,field)-getattr(expected,field))<1e-7,(field,a,normal,permutation)
        assert child.building_counts==expected.building_counts and child.purchased_upgrades==expected.purchased_upgrades
    assert bool(found)==(expected is not None)
    multiple+=found>1;rescued+=expected is not None and stock(s,a) is None
    if expected is not None:s=expected
    if (case+1)%500==0:print(json.dumps(dict(event='progress',cases=case+1,permutations=checked,valid=valid,rescued=rescued,elapsed=time.monotonic()-start)),flush=True)
result=dict(cases=case+1,permutations=checked,valid=valid,rescued=rescued,multiple_valid_orders=multiple,positive_bank_cases=positive,elapsed=time.monotonic()-start)
(work/'verify_partial_order.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(event='complete',**result)),flush=True)

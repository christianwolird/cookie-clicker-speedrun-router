"""Optimize a purchase order's errand boundaries with exact shop replay."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import random
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import RouteAction,load_route,write_route,execute_route,action_errands,initial_gamestate
from ccsr.routes.replay import apply_errand
from ccsr.errands.errandifier import _bulk_clicks
from local_search import edits


def partition(plan,actions,*,width=4,max_size=24,expand=False):
    initial=initial_gamestate(plan);target=plan.target
    if initial.selling_allowed: raise ValueError('This experiment requires no selling')
    cap=max((u.handmade_required for u in initial.upgrade_catalog.values() if u.price<target),default=0)
    if expand:
        actions=tuple(replace(a,quantity=1) for a in actions for _ in range(a.quantity))
    states=[[(initial,())]]+[[] for _ in actions]
    best=(initial.finish(target).age,())
    for end in range(1,len(actions)+1):
        candidates={}
        for size in range(1,min(max_size,end)+1):
            begin=end-size
            if not states[begin]:continue
            clicks=_bulk_clicks(actions[begin:end],initial.bulk_size)
            for ancestor,history in states[begin]:
                try: child,purchases=apply_errand(ancestor,clicks)
                except (KeyError,ValueError):continue
                if child.lifetime_cookies>=target:continue
                key=(child.bank,child.lifetime_cookies,min(child.handmade_cookies,cap))
                old=candidates.get(key)
                if old is None or child.age<old[0].age:
                    normalized=tuple(RouteAction.from_purchase(p) for p in purchases)
                    candidates[key]=(child,history+(normalized,))
        ordered=sorted(candidates.values(),key=lambda x:x[0].finish(target).age)
        states[end]=ordered[:width]
        if ordered:
            child,history=ordered[0];age=child.finish(target).age
            if age<best[0]:best=(age,history)
    return replace(plan,errands=best[1]),best[0]


def main():
    p=argparse.ArgumentParser();p.add_argument('--source',default='/tmp/ccsr-trained-12h-20260914/local_v1.route')
    p.add_argument('--name',default='partition_v1');p.add_argument('--seconds',type=float,default=1800)
    p.add_argument('--seed',type=int,default=14);p.add_argument('--expand',action='store_true')
    p.add_argument('--width',type=int,default=4);args=p.parse_args()
    work=Path('/tmp/ccsr-trained-12h-20260914');base=load_route(args.source);best=base
    initial_age=best_age=execute_route(best).final_gamestate.age
    rng=random.Random(args.seed);start=time.monotonic();end=start+args.seconds;next_progress=start+30
    tried=valid=0;seen=set();seeds=[best];out=work/f'{args.name}.route'
    buildings=['Cursor','Grandma','Farm','Mine','Factory']
    upgrade_catalog=initial_gamestate(base).upgrade_catalog
    def save():
        plan=replace(best,name=args.name,algorithm='experimental_partition_local_search',
                     beam_width=None,errand_search_width=None,ruler_scale=None,ruler_route=None,beam_max_expansions=None)
        assert abs(execute_route(plan).final_gamestate.age-best_age)<1e-8
        temporary=out.with_suffix('.pending.route');write_route(temporary,plan,overwrite=True);temporary.replace(out)
    save()
    print(json.dumps(dict(event='start',initial=best_age,parameters=vars(args))),flush=True)
    while time.monotonic()<end:
        seed=best if rng.random()<.85 else rng.choice(seeds)
        actions=list(seed.actions)
        if tried:
            operation=rng.choice(('quantity','quantity','move','insert','remove','swap'))
            i=rng.randrange(len(actions))
            if operation=='quantity':
                if actions[i].operation!='buy':continue
                actions[i]=replace(actions[i],quantity=rng.randint(1,10))
                if rng.random()<.25:
                    j=rng.randrange(len(actions))
                    if actions[j].operation=='buy':actions[j]=replace(actions[j],quantity=rng.randint(1,10))
            elif operation=='move':
                a=actions.pop(i);actions.insert(rng.randrange(len(actions)+1),a)
            elif operation=='remove':actions.pop(i)
            elif operation=='swap':
                j=rng.randrange(len(actions));actions[i],actions[j]=actions[j],actions[i]
            else:
                if rng.random()<.75:
                    a=RouteAction('buy',rng.choice(buildings),rng.choice((1,1,2,3,5,7,10,10)))
                else:
                    upgrades=[u for u in upgrade_catalog if upgrade_catalog[u].price<base.target and not any(a.item==u for a in actions)]
                    if not upgrades:continue
                    a=RouteAction('upgrade',rng.choice(upgrades))
                actions.insert(i,a)
        actions=tuple(actions)
        if actions in seen:continue
        seen.add(actions);tried+=1
        plan,age=partition(base,actions,width=args.width,expand=args.expand)
        valid+=1
        if age<best_age-1e-9:
            best=plan;best_age=age;save();seeds.append(best)
            seeds=seeds[-30:]
            print(json.dumps(dict(event='improvement',finish=age,elapsed=time.monotonic()-start,tried=tried)),flush=True)
        elif age<best_age+3 and rng.random()<.15:
            seeds.append(plan);seeds=seeds[-30:]
        if time.monotonic()>=next_progress:
            print(json.dumps(dict(event='progress',finish=best_age,elapsed=time.monotonic()-start,tried=tried,valid=valid)),flush=True)
            next_progress=time.monotonic()+30
    data=dict(finish=best_age,initial=initial_age,elapsed=time.monotonic()-start,tried=tried,valid=valid,parameters=vars(args),route=str(out))
    out.with_suffix('.json').write_text(json.dumps(data,indent=2)+'\n');save()
    print(json.dumps(dict(event='complete',**data)),flush=True)

if __name__=='__main__':main()

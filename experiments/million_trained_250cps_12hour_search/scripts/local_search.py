"""Replay-validated iterated local search; results are experimental artifacts."""
import argparse
from collections import OrderedDict
from dataclasses import replace
import json
from pathlib import Path
import random
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'src'))
from ccsr.config import load_route_profile
from ccsr.routes import RouteAction, action_errands, execute_route, load_route, use_route_profile, write_route


def edits(errands):
    for i, errand in enumerate(errands):
        yield errands[:i]+errands[i+1:]
        for j,a in enumerate(errand):
            removed=errand[:j]+errand[j+1:]
            yield errands[:i]+((removed,) if removed else ())+errands[i+1:]
            if a.operation=='buy':
                for q in range(1,11):
                    if q!=a.quantity:
                        yield errands[:i]+(errand[:j]+(replace(a,quantity=q),)+errand[j+1:],)+errands[i+1:]
            if j+1<len(errand):
                yield errands[:i]+(errand[:j]+(errand[j+1],a)+errand[j+2:],)+errands[i+1:]
                yield errands[:i]+(errand[:j+1],errand[j+1:])+errands[i+1:]
        if i+1<len(errands):
            nxt=errands[i+1]
            yield errands[:i]+(errand+nxt,)+errands[i+2:]
            yield errands[:i]+(nxt,errand)+errands[i+2:]
            if len(errand)>1:
                yield errands[:i]+(errand[:-1],(errand[-1],)+nxt)+errands[i+2:]
            if len(nxt)>1:
                yield errands[:i]+(errand+(nxt[0],),nxt[1:])+errands[i+2:]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--work',default='/tmp/ccsr-trained-12h-20260914')
    parser.add_argument('--seconds',type=float,default=7200)
    parser.add_argument('--seed',type=int,default=20260914)
    parser.add_argument('--name',default='local_v1')
    parser.add_argument('--source',action='append',default=[])
    args=parser.parse_args()
    work=Path(args.work); rng=random.Random(args.seed)
    profile=load_route_profile('million-250cps')
    paths=[work/'incumbent_start.route', ROOT/'routes/million-250cps/generated_greedy.route']
    paths+=list(Path('/tmp/ccsr-million-250cps-20260914').glob('*refined.route'))
    paths+=list(map(Path,args.source))
    seeds={}
    for path in paths:
        try:
            p=use_route_profile(load_route(path),profile)
            r=execute_route(p)
            if r.final_gamestate.age<212:
                seeds[action_errands(r)]=(r.final_gamestate.age,replace(p,errands=action_errands(r)))
        except (ValueError,KeyError):
            pass
    seeds=sorted(seeds.values(),key=lambda x:x[0])[:24]
    best_age,base=seeds[0]
    best=base
    initial_age=best_age
    start=time.monotonic(); end=start+args.seconds; next_progress=start+30
    tried=valid=restarts=improvements=0
    cache=OrderedDict()
    out=work/f'{args.name}.route'
    def score(errands):
        nonlocal tried,valid
        if errands in cache:
            return cache[errands]
        tried+=1
        try:
            r=execute_route(replace(base,errands=errands)); valid+=1
            v=(r.final_gamestate.age,action_errands(r))
        except (ValueError,KeyError):
            v=(float('inf'),errands)
        cache[errands]=v
        if len(cache)>150000:
            for _ in range(25000): cache.popitem(last=False)
        return v
    def save():
        p=replace(best,name=args.name,algorithm='experimental_iterated_local_search',
                  beam_width=None,errand_search_width=None,ruler_scale=None,
                  ruler_route=None,beam_max_expansions=None)
        assert abs(execute_route(p).final_gamestate.age-best_age)<1e-8
        temp=out.with_suffix('.pending.route')
        write_route(temp,p,comment='Replay-verified iterated local search; see experiments/million_trained_250cps_12hour_search/docs/trained-250cps-12h-search.md.',overwrite=True)
        temp.replace(out)
    save()
    print(json.dumps({'event':'start','initial':initial_age,'seed_routes':len(seeds),'parameters':vars(args)}),flush=True)
    while time.monotonic()<end:
        restarts+=1
        seed=best if rng.random()<.7 else rng.choice(seeds)[1]
        errands=seed.errands
        if restarts>1:
            for _ in range(rng.choice((1,2,3,4,5))):
                nearby=list(edits(errands)); rng.shuffle(nearby)
                previous=score(errands)[0]
                slack=rng.choice((1,3,6,12))
                for candidate in nearby:
                    age,normalized=score(candidate)
                    if age<previous+slack:
                        errands=normalized;break
        age,errands=score(errands)
        while time.monotonic()<end:
            improved=None
            for candidate in edits(errands):
                if time.monotonic()>=end: break
                candidate_age,normalized=score(candidate)
                if candidate_age<age-1e-9:
                    age=candidate_age; improved=normalized
            if improved is None: break
            errands=improved
        if age<best_age-1e-9:
            best_age=age;best=replace(base,errands=errands);improvements+=1
            save()
            print(json.dumps({'event':'improvement','finish':best_age,'elapsed':time.monotonic()-start,'restarts':restarts,'tried':tried}),flush=True)
        if time.monotonic()>=next_progress:
            print(json.dumps({'event':'progress','finish':best_age,'elapsed':time.monotonic()-start,'restarts':restarts,'tried':tried,'valid':valid}),flush=True)
            next_progress=time.monotonic()+30
    save()
    result=dict(finish=best_age,initial=initial_age,elapsed=time.monotonic()-start,tried=tried,valid=valid,restarts=restarts,improvements=improvements,route=str(out),parameters=vars(args))
    out.with_suffix('.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'event':'complete',**result}),flush=True)

if __name__=='__main__': main()

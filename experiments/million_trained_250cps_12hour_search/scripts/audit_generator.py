"""Measure known-route neighbor coverage, runtime, and strategy duplication."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route, initial_gamestate, apply_errand
from ccsr.errands.generator import generate_neighbors as original
from generator_variants import Options, generate_neighbors, strategy_key


def outcome(state):
    return (tuple(state.building_counts.values()),frozenset(state.purchased_upgrades),
            round(state.bank,6),round(state.lifetime_cookies,6),round(min(state.handmade_cookies,1000),6))


def job(payload):
    label,kwargs,options,index,state,wanted,actions=payload
    start=time.monotonic()
    neighbors=(original(state,1_000_000,**kwargs) if options is None else
               generate_neighbors(state,1_000_000,**kwargs,options=Options(**options)))
    rank=next((i+1 for i,n in enumerate(neighbors) if outcome(n.gamestate)==outcome(wanted)),None)
    strategies=len(set(strategy_key(n,state,'upgrade_building') for n in neighbors))
    distinct=len(set(outcome(n.gamestate) for n in neighbors))
    return dict(variant=label,index=index,rank=rank,returned=len(neighbors),distinct=distinct,
                strategies=strategies,elapsed=time.monotonic()-start,
                wanted_score=(wanted.age-state.age)*wanted.cps()/(wanted.cps()-state.cps()),
                best_score=neighbors[0].score if neighbors else None,
                worst_score=neighbors[-1].score if neighbors else None,
                actions=[asdict(a) for a in actions])


def main():
    p=argparse.ArgumentParser();p.add_argument('--route',default='/tmp/ccsr-trained-12h-20260914/incumbent_start.route')
    p.add_argument('--suite',default='initial');p.add_argument('--name',default='audit_initial');p.add_argument('--workers',type=int,default=4)
    p.add_argument('--work',default='/tmp/ccsr-trained-12h-20260914');args=p.parse_args()
    work=Path(args.work);plan=load_route(args.route)
    samples=[];state=initial_gamestate(plan)
    for i,actions in enumerate(plan.errands,1):
        child,_=apply_errand(state,actions)
        samples.append((i,state,child,actions));state=child
    small=dict(width=20,search_width=40,queue_expansions=100,price_horizon_multiplier=16)
    wide=dict(width=120,search_width=240,queue_expansions=500,price_horizon_multiplier=16)
    variants=[('stock20',small,None),('stock120',wide,None),
              ('no_stop',small,dict(early_stop=False)),
              ('distinct',small,dict(early_stop=False,distinct_results=True)),
              ('bonus05',small,dict(early_stop=False,distinct_results=True,upgrade_bonus=.05)),
              ('bonus10',small,dict(early_stop=False,distinct_results=True,upgrade_bonus=.1)),
              ('bonus20',small,dict(early_stop=False,distinct_results=True,upgrade_bonus=.2)),
              ('diverse',small,dict(early_stop=False,distinct_results=True,diverse_queue=2,diverse_results=2)),
              ('diverse_bonus10',small,dict(early_stop=False,distinct_results=True,diverse_queue=2,diverse_results=2,upgrade_bonus=.1)),
              ('upgrade_diversity',small,dict(early_stop=False,distinct_results=True,diverse_queue=3,diverse_results=3,strategy='upgrades'))]
    if args.suite=='access':
        common=dict(early_stop=False,distinct_results=True,all_evaluated=True)
        variants=[('all_evaluated',small,common),
                  ('all_diverse',small,dict(common,diverse_queue=2,diverse_results=2)),
                  ('all_balanced',small,dict(common,diverse_queue=2,diverse_results=2,expansion_balance=.05)),
                  ('all_balanced_bonus10',small,dict(common,diverse_queue=2,diverse_results=2,expansion_balance=.05,upgrade_bonus=.1)),
                  ('reserved8',small,dict(common,seed_reserve=8)),
                  ('balanced_reserved8',small,dict(common,diverse_queue=2,diverse_results=2,expansion_balance=.05,seed_reserve=8)),
                  ('balanced_reserved12',small,dict(common,diverse_queue=2,diverse_results=2,expansion_balance=.1,seed_reserve=12)),
                  ('balanced_wide',dict(small,width=40,search_width=80,queue_expansions=200),dict(common,diverse_queue=2,diverse_results=2,expansion_balance=.05,seed_reserve=10))]
    if args.suite=='canonical':
        common=dict(early_stop=False,distinct_results=True,all_evaluated=True,canonical_full_core=True)
        variants=[('canonical',small,common),
                  ('canonical_bonus10',small,dict(common,upgrade_bonus=.1)),
                  ('canonical_reserved',small,dict(common,seed_reserve=8)),
                  ('canonical_balanced',small,dict(common,diverse_queue=2,diverse_results=2,expansion_balance=.05,seed_reserve=8)),
                  ('canonical_wide',dict(small,width=40,search_width=80,queue_expansions=300),dict(common,diverse_queue=2,diverse_results=2,expansion_balance=.05,seed_reserve=10))]
    if args.suite=='projection':
        common=dict(early_stop=False,distinct_results=True,all_evaluated=True,canonical_full_core=True,fast_evaluation=True)
        variants=[('projection10k_025',small,dict(common,projection_budget=10000,projection_weight=.25)),
                  ('projection50k_025',small,dict(common,projection_budget=50000,projection_weight=.25)),
                  ('projection50k_050',small,dict(common,projection_budget=50000,projection_weight=.5)),
                  ('projection50k_100',small,dict(common,projection_budget=50000,projection_weight=1)),
                  ('projection_reserved',small,dict(common,projection_budget=50000,projection_weight=.5,seed_reserve=8)),
                  ('projection_balanced',small,dict(common,projection_budget=50000,projection_weight=.5,diverse_queue=2,diverse_results=2,expansion_balance=.05,seed_reserve=8))]
    tasks=[(name,kwargs,options,*sample) for name,kwargs,options in variants for sample in samples]
    start=time.monotonic();rows=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(job,t) for t in tasks]
        for future in as_completed(futures):
            row=future.result();rows.append(row)
            with (work/f'{args.name}.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            print(json.dumps(row),flush=True)
    summaries=[]
    for name,kwargs,options in variants:
        group=sorted([r for r in rows if r['variant']==name],key=lambda r:r['index'])
        summaries.append(dict(variant=name,hits=sum(r['rank'] is not None for r in group),total=len(group),
                              ranks=[r['rank'] for r in group],elapsed=sum(r['elapsed'] for r in group),
                              distinct=sum(r['distinct'] for r in group),returned=sum(r['returned'] for r in group),
                              strategies=sum(r['strategies'] for r in group),kwargs=kwargs,options=options))
    result=dict(route=args.route,elapsed=time.monotonic()-start,variants=summaries)
    (work/f'{args.name}.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'event':'complete',**result}),flush=True)

if __name__=='__main__': main()

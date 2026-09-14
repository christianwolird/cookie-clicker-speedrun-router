import argparse
from dataclasses import replace,asdict
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from generator_variants import Options,generate_neighbors
from audit_generator import outcome
work=Path('/tmp/ccsr-trained-12h-20260914')
p=argparse.ArgumentParser();p.add_argument('--route',default=str(work/'incumbent_start.route'));p.add_argument('--name',default='audit_native');args=p.parse_args()
plan=load_route(args.route);samples=[];state=initial_gamestate(plan)
for actions in plan.errands:
    child,_=apply_errand(state,actions);samples.append((state,child));state=child
common=Options(native_backend=True,canonical_full_core=True,early_stop=False,all_evaluated=True)
variants=[('native20',20,40,100,common),('native80',80,160,500,common),
          ('native_anchors',80,160,500,replace(common,native_anchor_all=True)),
          ('native_diverse',80,160,500,replace(common,diverse_queue=3,diverse_results=3,seed_reserve=12)),
          ('native_lookahead',80,160,500,replace(common,two_step_pool=400,two_step_weight=1)),
          ('native_lookahead_anchors',80,160,500,replace(common,two_step_pool=400,two_step_weight=1,native_anchor_all=True)),
          ('native_wide',160,400,2000,replace(common,two_step_pool=800,two_step_weight=.5,seed_reserve=12,diverse_results=3))]
rows=[]
for label,width,inner,expansions,options in variants:
    start=time.monotonic();ranks=[]
    for i,(state,wanted) in enumerate(samples,1):
        ns=generate_neighbors(state,plan.target,width=width,search_width=inner,queue_expansions=expansions,price_horizon_multiplier=16,max_errand_actions=12,options=options)
        rank=next((j+1 for j,n in enumerate(ns) if outcome(n.gamestate)==outcome(wanted)),None);ranks.append(rank)
    row=dict(variant=label,ranks=ranks,hits=sum(r is not None for r in ranks),elapsed=time.monotonic()-start,width=width,inner=inner,expansions=expansions,options=asdict(options));rows.append(row);print(json.dumps(row),flush=True)
(work/f'{args.name}.json').write_text(json.dumps(rows,indent=2)+'\n')

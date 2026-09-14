import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from generator_variants import Options,generate_neighbors
from audit_generator import outcome
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'incumbent_start.route');state=initial_gamestate(plan)
rows=[];start=time.monotonic()
options=Options(early_stop=False,distinct_results=True,all_evaluated=True,canonical_full_core=True,fast_evaluation=True,seed_reserve=10,diverse_queue=2,diverse_results=2,expansion_balance=.05)
for i,actions in enumerate(plan.errands,1):
    desired,_=apply_errand(state,actions)
    trace=[];ns=generate_neighbors(state,plan.target,width=40,search_width=160,queue_expansions=1000,price_horizon_multiplier=16,options=options,trace=trace)
    found=[n for n in trace if outcome(n.gamestate)==outcome(desired)]
    row=dict(index=i,evaluated=len(trace),found=bool(found),returned=any(outcome(n.gamestate)==outcome(desired) for n in ns),
             raw_rank=None if not found else sum(n.score<found[0].score for n in trace)+1)
    rows.append(row);print(json.dumps(row),flush=True);state=desired
(work/'trace_witness.json').write_text(json.dumps(dict(elapsed=time.monotonic()-start,rows=rows),indent=2)+'\n')

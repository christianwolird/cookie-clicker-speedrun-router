from dataclasses import replace,asdict
import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from generator_variants import Options,generate_neighbors
from audit_generator import outcome
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'native_local_cool.route');samples=[];state=initial_gamestate(plan)
for actions in plan.errands:
    child,_=apply_errand(state,actions);samples.append((state,child));state=child
common=Options(native_backend=True,canonical_full_core=True,early_stop=False,all_evaluated=True,upgrade_macros=True,native_anchor_all=True)
variants=[('partial80',80,160,500,replace(common,native_anchor_all=4,canonical_partial=True)),('partial160',160,400,1000,replace(common,native_anchor_all=4,canonical_partial=True)),('partial160_mouse',160,400,1000,replace(common,native_anchor_all=4,canonical_partial=True,future_upgrade_mask=32768)),('partial400_mouse',400,1000,2000,replace(common,native_anchor_all=4,canonical_partial=True,future_upgrade_mask=32768))]
rows=[]
for label,width,inner,expansions,options in variants:
    start=time.monotonic();ranks=[]
    for i,(state,wanted) in enumerate(samples,1):
        ns=generate_neighbors(state,plan.target,width=width,search_width=inner,queue_expansions=expansions,price_horizon_multiplier=None,max_errand_actions=12,options=options)
        ranks.append(next((j+1 for j,n in enumerate(ns) if outcome(n.gamestate)==outcome(wanted)),None))
    row=dict(variant=label,ranks=ranks,hits=sum(r is not None for r in ranks),elapsed=time.monotonic()-start,width=width,inner=inner,expansions=expansions,options=asdict(options));rows.append(row);print(json.dumps(row),flush=True)
(work/'audit_native_partial.json').write_text(json.dumps(rows,indent=2)+'\n')

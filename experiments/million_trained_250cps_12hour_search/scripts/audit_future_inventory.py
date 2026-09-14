"""Score future buildings using later inventories from the current ruler."""
from dataclasses import replace
import json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from generator_variants import Options,generate_neighbors
from audit_generator import outcome
from native_bridge import BUILDINGS
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'session_best.route');samples=[];state=initial_gamestate(plan)
states=[state]
for actions in plan.errands:
    child,_=apply_errand(state,actions);samples.append((state,child));state=child;states.append(state)
common=Options(native_backend=True,canonical_full_core=True,canonical_partial=True,quantity_children=1,
               early_stop=False,all_evaluated=True,upgrade_macros=True,native_anchor_all=4)
rows=[]
for mask in (0,32768):
    for fraction in (0,.02,.1,.25,.5):
        start=time.monotonic();ranks=[]
        for state,wanted in samples:
            baked=state.lifetime_cookies+fraction*(1e6-state.lifetime_cookies)
            target=next((s for s in states if s.lifetime_cookies>=baked),states[-1])
            counts=tuple(max(0,target.building_counts[b]-state.building_counts[b]) for b in BUILDINGS) if fraction else ()
            options=replace(common,future_upgrade_mask=mask,future_counts=counts)
            ns=generate_neighbors(state,plan.target,width=160,search_width=400,queue_expansions=1000,price_horizon_multiplier=None,options=options)
            ranks.append(next((j+1 for j,n in enumerate(ns) if outcome(n.gamestate)==outcome(wanted)),None))
        row=dict(mask=mask,fraction=fraction,hits=sum(r is not None for r in ranks),ranks=ranks,elapsed=time.monotonic()-start)
        rows.append(row);print(json.dumps(row),flush=True)
(work/'audit_future_inventory.json').write_text(json.dumps(rows,indent=2)+'\n')

import ctypes as C,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from native_bridge import *
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'session_best.route');s=initial_gamestate(plan);samples=[]
for actions in plan.errands:
    child,_=apply_errand(s,actions);samples.append((pack_state(s),pack_state(child)));s=child
rows=[]
for mode,pops in ((0,5000),(1,5000),(2,5000),(1,20000),(2,20000)):
    options=NativeOptions(width=2500,search_width=2000,pops=pops,max_actions=12,canonical=1,canonical_partial=1,all_evaluated=1,anchor_all=4,upgrade_macros=1,future_upgrade_mask=32768,future_weight=1,horizon=0,quantity_children=mode)
    begin=time.monotonic();cpu=time.process_time();ranks=[];total=0
    for a,b in samples:
        out=(NativeNeighbor*2500)();n=LIB.native_generate(C.byref(a),C.byref(options),out,len(out));total+=n
        ranks.append(next((i+1 for i in range(n) if list(out[i].state.buildings)==list(b.buildings) and out[i].state.upgrades==b.upgrades and abs(out[i].state.baked-b.baked)<1e-6 and abs(out[i].state.bank-b.bank)<1e-6),None))
    row=dict(mode=mode,pops=pops,width=2500,inner=2000,hits=sum(x is not None for x in ranks),ranks=ranks,returned=total,cpu=time.process_time()-cpu,wall=time.monotonic()-begin);rows.append(row);print(json.dumps(row),flush=True)
(work/'benchmark_quantity.json').write_text(json.dumps(rows,indent=2)+'\n')

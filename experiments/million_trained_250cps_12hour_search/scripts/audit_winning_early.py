"""Check exposure of the new guided route's errands across breadth settings."""
import ctypes as C,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,write_route,initial_gamestate,apply_errand
from native_bridge import LIB,NativeOptions,NativeNeighbor,pack_state
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'session_best.route')
write_route(work/'audit_winning_early_source.route',plan,overwrite=True)
state=initial_gamestate(plan);samples=[]
for actions in plan.errands:
    child,_=apply_errand(state,actions);samples.append((pack_state(state),pack_state(child)));state=child
def key(s):return tuple(s.buildings)+(s.upgrades,round(s.bank,9),round(s.baked,9),round(min(s.handmade,1000),9))
rows=[]
for width,inner,pops in ((400,800,2000),(1200,1500,5000),(2500,2000,10000)):
    for mode in (1,4):
        options=NativeOptions(width=width,search_width=inner,pops=pops,max_actions=12,canonical=1,canonical_partial=1,
                              all_evaluated=1,anchor_all=4,upgrade_macros=1,future_upgrade_mask=32768,future_weight=1,horizon=0,quantity_children=mode)
        cpu=0.;ranks=[]
        for state,wanted in samples:
            out=(NativeNeighbor*width)();start=time.process_time()
            count=LIB.native_generate(C.byref(state),C.byref(options),out,len(out));cpu+=time.process_time()-start
            target=key(wanted);ranks.append(next((j+1 for j in range(count) if key(out[j].state)==target),None))
        row=dict(width=width,inner=inner,pops=pops,quantity_mode=mode,cpu=cpu,hits=sum(r is not None for r in ranks),ranks=ranks)
        rows.append(row);print(json.dumps(row),flush=True)
(work/'audit_winning_early.json').write_text(json.dumps(rows,indent=2)+'\n')

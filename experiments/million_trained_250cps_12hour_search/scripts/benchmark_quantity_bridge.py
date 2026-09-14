"""Compare first-feasible quantity growth on incumbent states."""
import ctypes as C,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from native_bridge import LIB,NativeOptions,NativeNeighbor,pack_state,unpack_state
from audit_generator import outcome
work=Path('/tmp/ccsr-trained-12h-20260914');base=load_route(work/'session_best.route');s=initial_gamestate(base);samples=[]
for actions in base.errands:
    child,_=apply_errand(s,actions);samples.append((s,child));s=child
rows=[]
for mode in (1,4,2,5):
    options=NativeOptions(width=2500,search_width=2000,pops=5000,max_actions=12,canonical=1,canonical_partial=1,
                          all_evaluated=1,anchor_all=4,upgrade_macros=1,future_upgrade_mask=32768,future_weight=1,horizon=0,quantity_children=mode)
    cpu=0.;ranks=[];returned=0
    for state,wanted in samples:
        packed=pack_state(state);out=(NativeNeighbor*2500)();start=time.process_time()
        n=LIB.native_generate(C.byref(packed),C.byref(options),out,len(out));cpu+=time.process_time()-start;returned+=n
        ranks.append(next((j+1 for j in range(n) if outcome(unpack_state(out[j].state,state))==outcome(wanted)),None))
    row=dict(mode=mode,cpu=cpu,returned=returned,hits=sum(r is not None for r in ranks),ranks=ranks);rows.append(row);print(json.dumps(row),flush=True)
(work/'benchmark_quantity_bridge.json').write_text(json.dumps(rows,indent=2)+'\n')

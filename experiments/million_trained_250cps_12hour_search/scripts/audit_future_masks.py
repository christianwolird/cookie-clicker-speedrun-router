"""Find prospective-upgrade scoring failures without running entire beams."""
import ctypes as C,itertools,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from native_bridge import *
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'native_local_cool.route');s=initial_gamestate(plan);samples=[]
for actions in plan.errands:
    b,_=apply_errand(s,actions);samples.append((pack_state(s),pack_state(b)));s=b
masks={0,32768,32776}
for i in range(len(UPGRADES)):masks.add(32768|(1<<i))
for i,j in itertools.combinations((4,5,6,7,8,10,12),2):masks.add(32768|(1<<i)|(1<<j))
rows=[]
for mask in sorted(masks):
    options=NativeOptions(width=160,search_width=400,pops=1000,max_actions=12,canonical=1,all_evaluated=1,anchor_all=4,upgrade_macros=1,horizon=0,future_upgrade_mask=mask,future_weight=1)
    start=time.monotonic();ranks=[]
    for a,b in samples:
        out=(NativeNeighbor*160)();count=LIB.native_generate(C.byref(a),C.byref(options),out,len(out))
        ranks.append(next((i+1 for i in range(count) if list(out[i].state.buildings)==list(b.buildings) and out[i].state.upgrades==b.upgrades and abs(out[i].state.baked-b.baked)<1e-6 and abs(out[i].state.bank-b.bank)<1e-6),None))
    row=dict(mask=mask,upgrades=[u for i,u in enumerate(UPGRADES) if mask&(1<<i)],hits=sum(i is not None for i in ranks),ranks=ranks,elapsed=time.monotonic()-start);rows.append(row);print(json.dumps(row),flush=True)
(work/'audit_future_masks.json').write_text(json.dumps(rows,indent=2)+'\n')

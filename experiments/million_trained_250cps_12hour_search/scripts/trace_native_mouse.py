import ctypes as C
from pathlib import Path
import sys,time,json
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from generator_variants import canonical_full_core
from native_bridge import *
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'native_local_cool.route');state=initial_gamestate(plan)
for step,actions in enumerate(plan.errands,1):
    wanted,_=apply_errand(state,actions)
    if step in (5,6):
        for forced in (0,):
            options=NativeOptions(width=100000,search_width=1000,pops=5000,max_actions=12,canonical=1,all_evaluated=1,anchor_all=4,upgrade_macros=1,expand_seeds=forced,horizon=0,future_upgrade_mask=32768,future_weight=1)
            out=(NativeNeighbor*100000)();packed=pack_state(state);want=pack_state(wanted);start=time.monotonic()
            count=LIB.native_generate(C.byref(packed),C.byref(options),out,len(out));matches=[];family=[]
            for i in range(count):
                n=out[i]
                same_upgrade=n.state.upgrades==want.upgrades
                delta=[n.state.buildings[j]-packed.buildings[j] for j in range(len(BUILDINGS))]
                wanted_delta=[want.buildings[j]-packed.buildings[j] for j in range(len(BUILDINGS))]
                if same_upgrade and [q>0 for q in delta]==[q>0 for q in wanted_delta] and len(family)<10:
                    family.append(dict(rank=i+1,counts=delta,score=n.score,raw=n.raw_score))
                if list(n.state.buildings)==list(want.buildings) and n.state.upgrades==want.upgrades:
                    matches.append(dict(rank=i+1,raw=n.raw_score,score=n.score,baked_delta=n.state.baked-want.baked,bank_delta=n.state.bank-want.bank,age_delta=n.state.age-want.age,actions=[str(a) for a in unpack_actions(n.actions[:n.action_count])]))
            print(json.dumps(dict(step=step,forced=forced,count=count,matches=matches,family=family,elapsed=time.monotonic()-start)),flush=True)
    state=wanted

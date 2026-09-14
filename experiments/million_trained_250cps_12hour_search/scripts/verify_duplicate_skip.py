"""Compare every returned native byte with the pre-optimization library."""
import ctypes as C,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from native_bridge import *
work=Path('/tmp/ccsr-trained-12h-20260914');old=C.CDLL(str(work/'native_before_skip.so'))
old.native_generate.argtypes=LIB.native_generate.argtypes;old.native_generate.restype=C.c_int
# Later options append a future-count array; these comparisons leave it zero.
# The original ABI prefix stays identical and the old library reads only it.
assert old.native_options_size()==NativeOptions.future_counts.offset==120
plan=load_route(work/'session_best.route');s=initial_gamestate(plan);samples=[pack_state(s)]
for a in plan.errands:s,_=apply_errand(s,a);samples.append(pack_state(s))
rows=[];checked=0
for mode,partial,mask in ((0,0,0),(0,1,0),(0,1,32768),(1,1,32768),(2,1,32768),(3,1,32768)):
    cpu=[0.,0.];returned=0
    options=NativeOptions(width=400,search_width=800,pops=2000,max_actions=12,canonical=1,canonical_partial=partial,all_evaluated=1,anchor_all=4,upgrade_macros=1,future_upgrade_mask=mask,future_weight=1,horizon=0,quantity_children=mode)
    for state in samples:
        outputs=[]
        for i,library in enumerate((old,LIB)):
            out=(NativeNeighbor*400)();start=time.process_time();n=library.native_generate(C.byref(state),C.byref(options),out,len(out));cpu[i]+=time.process_time()-start
            outputs.append((n,bytes(out)[:n*C.sizeof(NativeNeighbor)]))
        assert outputs[0]==outputs[1],(mode,partial,mask,state)
        checked+=1;returned+=outputs[0][0]
    row=dict(mode=mode,partial=partial,mask=mask,states=len(samples),returned=returned,before_cpu=cpu[0],after_cpu=cpu[1],speedup=cpu[0]/cpu[1]);rows.append(row);print(json.dumps(row),flush=True)
(work/'verify_duplicate_skip.json').write_text(json.dumps(dict(checked=checked,rows=rows),indent=2)+'\n')

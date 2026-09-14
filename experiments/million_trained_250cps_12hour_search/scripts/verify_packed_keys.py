"""Check exact generator/search outputs and measure packed-key memory."""
import ctypes as C,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from native_bridge import LIB,NativeOptions,NativeNeighbor,pack_state,pack_actions
work=Path('/tmp/ccsr-trained-12h-20260914');old=C.CDLL(str(work/'native_before_packed_keys.so'))
old.native_generate.argtypes=LIB.native_generate.argtypes;old.native_generate.restype=C.c_int
assert old.native_options_size()==C.sizeof(NativeOptions)
plan=load_route(work/'session_best.route');state=initial_gamestate(plan);samples=[pack_state(state)]
for actions in plan.errands:state,_=apply_errand(state,actions);samples.append(pack_state(state))
checks=0
for mode,counts in ((0,False),(1,False),(4,False),(5,False),(4,True)):
    options=NativeOptions(width=400,search_width=800,pops=2000,max_actions=12,canonical=1,canonical_partial=1,
                          all_evaluated=1,anchor_all=4,upgrade_macros=1,future_upgrade_mask=32768,future_weight=1,horizon=0,quantity_children=mode)
    if counts:options.future_counts=(C.c_int*5)(10,10,10,3,0)
    for state in samples:
        outputs=[]
        for library in (old,LIB):
            out=(NativeNeighbor*400)();n=library.native_generate(C.byref(state),C.byref(options),out,len(out))
            outputs.append((n,bytes(out)[:n*C.sizeof(NativeNeighbor)]))
        assert outputs[0]==outputs[1],(mode,counts);checks+=1
print(json.dumps(dict(event='generator_checks',identical=checks)),flush=True)
seed=work/'packed_benchmark.seed';seed.write_text(str(len(plan.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(map(str,pack_actions(e))) for e in plan.errands)+'\n')
rows=[];previous=None
for binary in ('native_beam_before_packed_keys','native_beam'):
    command=['/usr/bin/time','-f','{"rss_kib":%M,"cpu_user":%U,"cpu_system":%S}',str(work/binary),
             '--seed',str(seed),'--seconds','120','--expansions','10000','--workers','2',
             '--width','160','--inner','400','--pops','1000','--horizon','0','--order','1',
             '--stage-balance','1','--quantity-children','4','--canonical-partials','1',
             '--future-mask','32768','--persistent-workers','1','--hand-dominance','1','--rollout','0',
             '--seed-prefixes','0','--report-generated','1']
    result=subprocess.run(command,capture_output=True,text=True,check=True)
    data=[json.loads(line) for line in result.stdout.splitlines()];last=data[-1];usage=json.loads(result.stderr)
    signature=[(r['finish'],r['route']) for r in data if 'route' in r]
    signature.append({k:last[k] for k in ('expanded','generated','nodes','expanded_by_baked','hand_rejected','hand_invalidated')})
    assert last['termination']=='expansion_limit'
    if previous is not None:assert signature==previous
    previous=signature;row=dict(binary=binary,wall=last['elapsed'],**usage,**{k:last[k] for k in ('expanded','generated','nodes')});rows.append(row);print(json.dumps(row),flush=True)
(work/'verify_packed_keys.json').write_text(json.dumps(dict(generator_checks=checks,benchmarks=rows),indent=2)+'\n')

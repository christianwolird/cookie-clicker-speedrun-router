"""Run compiled beam experiments and replay-validate each reported improvement."""
import argparse
import fcntl
import hashlib
from dataclasses import replace
import json
import resource
from pathlib import Path
import shutil
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,write_route,execute_route,action_errands
from native_bridge import pack_actions,unpack_actions
from experiment_paths import WORK

p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--source',default='/tmp/ccsr-trained-12h-20260914/local_v1.route')
p.add_argument('--seconds',type=float,default=600);p.add_argument('--options-json',default='{}');args=p.parse_args()
work=WORK;work.mkdir(parents=True,exist_ok=True)
retired=work/'retired_trial_prefixes.json'
if retired.exists() and any(args.name.startswith(prefix) for prefix in json.loads(retired.read_text())):
    raise SystemExit(f'Trial namespace retired by the experiment controller: {args.name}')
lease=(work/f'{args.name}.lock').open('a')
try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(f'Another controller owns trial {args.name}')
base=load_route(args.source);seedfile=work/f'{args.name}.seed'
source=work/f'{args.name}_source.route';write_route(source,base,overwrite=True)
snapshot=work/'snapshots'/args.name;snapshot.mkdir(parents=True,exist_ok=True)
for path in Path(__file__).parent.iterdir():
    if path.suffix in ('.py','.cpp','.hpp','.json'):shutil.copyfile(path,snapshot/path.name)
seedfile.write_text(str(len(base.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(str(c) for c in pack_actions(e)) for e in base.errands)+'\n')
options=json.loads(args.options_json);cmd=[str(work/'native_beam'),'--seed',str(seedfile),'--seconds',str(args.seconds),'--stop-file',str(work/f'{args.name}.stop')]
binary=snapshot/'native_beam';shutil.copy2(work/'native_beam',binary);cmd[0]=str(binary)
binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()
for key,value in options.items():cmd+=['--'+key,str(int(value) if isinstance(value,bool) else value)]
start=time.monotonic();initial=best=execute_route(base).final_gamestate.age;rows=[];candidate_count=0
usage=resource.getrusage(resource.RUSAGE_CHILDREN);cpu_before=usage.ru_utime+usage.ru_stime
process=subprocess.Popen(cmd,stdout=subprocess.PIPE,text=True);(work/f'{args.name}.pid').write_text(str(process.pid))
print(json.dumps(dict(event='parameters',name=args.name,options=options,seconds=args.seconds,source=str(source),initial=initial)),flush=True)
for line in process.stdout:
    row=json.loads(line)
    if 'route' in row:
        plan=replace(base,name=args.name,algorithm='experimental_native_beam',
                     errands=tuple(unpack_actions(e) for e in row['route']),beam_width=options.get('width',160),
                     errand_search_width=options.get('inner',400),errand_queue_depth=options.get('pops',1000),
                     price_horizon_multiplier=options.get('horizon',16) or None,max_errand_actions=options.get('max-actions',12),
                     ruler_scale=options.get('prune',.94),ruler_route=str(source),beam_max_expansions=options.get('expansions') or None)
        result=execute_route(plan)
        if abs(result.final_gamestate.age-row['finish'])>1e-7:
            process.terminate();raise AssertionError((result.final_gamestate.age,row))
        row['python_finish']=result.final_gamestate.age;row['replay_verified']=True
        if row['event']=='generated_best':
            generated_path=work/f'{args.name}_generated.route'
            write_route(generated_path,replace(plan,errands=action_errands(result)),comment='Best directly generated completion, excluding ruler-suffix rollouts.',overwrite=True)
            row['generated_path']=str(generated_path)
        if row['event']=='candidate':
            candidate_count+=1;directory=work/f'{args.name}_candidates';directory.mkdir(exist_ok=True)
            candidate_path=directory/f'candidate_{candidate_count:03d}.route'
            write_route(candidate_path,replace(plan,errands=action_errands(result)),comment='Replay-verified near-miss route retained as a local-search seed.',overwrite=True)
            row['candidate_path']=str(candidate_path)
        if result.final_gamestate.age<=best+1e-8:
            best=result.final_gamestate.age;plan=replace(plan,errands=action_errands(result))
            temporary=work/f'{args.name}.pending.route';write_route(temporary,plan,comment='Experimental native beam; every improvement validated with Python replay.',overwrite=True);temporary.replace(work/f'{args.name}.route')
    rows.append(row)
    with (work/f'{args.name}.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
code=process.wait()
if code:raise SystemExit(code)
usage=resource.getrusage(resource.RUSAGE_CHILDREN)
direct_finish=next((row['python_finish'] for row in reversed(rows) if row['event']=='generated_best'),None)
summary=dict(name=args.name,finish=best,direct_finish=direct_finish,initial=initial,elapsed=time.monotonic()-start,cpu_seconds=usage.ru_utime+usage.ru_stime-cpu_before,parameters=vars(args),options=options,binary=str(binary),binary_sha256=binary_sha256,last=rows[-1],route=str(work/f'{args.name}.route'))
(work/f'{args.name}.json').write_text(json.dumps(summary,indent=2)+'\n')
with (work/'native_beam_results.jsonl').open('a') as f:f.write(json.dumps(summary)+'\n')

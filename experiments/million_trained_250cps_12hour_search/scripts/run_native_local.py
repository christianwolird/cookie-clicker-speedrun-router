"""Run native route/order refinement, validating every reported best in Python."""
import argparse
import fcntl
import hashlib
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import shutil
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,write_route,execute_route,action_errands
from ccsr.routes import use_route_profile
from ccsr.config import load_route_profile
from native_bridge import pack_actions,unpack_actions
from experiment_paths import WORK

p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--source',default='/tmp/ccsr-trained-12h-20260914/local_v1.route')
p.add_argument('--seconds',type=float,default=3600);p.add_argument('--seed',type=int,default=101)
p.add_argument('--width',type=int,default=2);p.add_argument('--max-size',type=int,default=16)
p.add_argument('--tmax',type=float,default=3);p.add_argument('--tmin',type=float,default=.03);p.add_argument('--cycle',type=int,default=1500)
p.add_argument('--errand-bias',type=float,default=0);p.add_argument('--action-bias',type=float,default=0)
p.add_argument('--extra-source',action='append',default=[]);p.add_argument('--extra-directory',action='append',default=[])
p.add_argument('--expand',action='store_true');p.add_argument('--blocks',action='store_true')
p.add_argument('--canonical-partition',action='store_true');p.add_argument('--canonical-partials',action='store_true')
p.add_argument('--aggregate-partition',action='store_true',help='Collect each candidate errand into building totals before canonical x10 ordering')
p.add_argument('--lock-upgrades',action='store_true');p.add_argument('--restart-best',type=float,default=.75)
p.add_argument('--cache-size',type=int,default=0);p.add_argument('--trials',type=int,default=0)
p.add_argument('--quantity-order',type=int,default=0);p.add_argument('--partition-age-bound',action='store_true')
p.add_argument('--quantity-start',type=int,help='First combination index, inclusive, in a fixed-sequence scan')
p.add_argument('--quantity-deletions',action='store_true',help='Scan only quantity combinations that delete at least one building purchase')
p.add_argument('--quantity-end',type=int,help='Last combination index, exclusive; defaults to the full neighborhood')
p.add_argument('--quantity-cube-minimum',type=int,help='Scan +/-1 changes (including zero), changing at least this many positions')
args=p.parse_args()
cube=args.quantity_cube_minimum is not None
if cube and (args.quantity_order or args.quantity_deletions or not 0<=args.quantity_cube_minimum<=32):
    p.error('Quantity cubes require a minimum from 0 to 32 and exclude other quantity modes')
quantity_range=cube or args.quantity_deletions or args.quantity_start is not None or args.quantity_end is not None
if quantity_range and ((not args.quantity_order and not cube) or args.partition_age_bound):
    p.error('Quantity scans require an order or cube minimum and do not use the partition age bound')
if quantity_range and (args.quantity_start is not None and args.quantity_start<0 or args.quantity_end is not None and args.quantity_end<(args.quantity_start or 0)):
    p.error('Quantity range indices must be nonnegative and end must not precede start')
if args.aggregate_partition and (args.quantity_order or cube):
    p.error('Aggregated partitioning is a separate neighborhood from fixed-order quantity scans')
if args.canonical_partials:args.canonical_partition=True
work=WORK;work.mkdir(parents=True,exist_ok=True)
retired=work/'retired_trial_prefixes.json'
if retired.exists() and any(args.name.startswith(prefix) for prefix in json.loads(retired.read_text())):
    raise SystemExit(f'Trial namespace retired by the experiment controller: {args.name}')
lease=(work/f'{args.name}.lock').open('a')
try:fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit(f'Another controller owns trial {args.name}')
base=load_route(args.source);seedfile=work/f'{args.name}.seed'
write_route(work/f'{args.name}_source.route',base,overwrite=True)
extra_paths=args.extra_source+[str(p) for d in args.extra_directory for p in sorted(Path(d).glob('*.route'))]
seeds=[base]+[use_route_profile(load_route(p),load_route_profile('million-250cps')) for p in extra_paths]
seedfile.write_text(''.join(str(len(seed.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(str(c) for c in pack_actions(e)) for e in seed.errands)+'\n' for seed in seeds))
snapshot=work/'snapshots'/args.name;snapshot.mkdir(parents=True,exist_ok=True)
for path in Path(__file__).parent.iterdir():
    if path.suffix in ('.py','.cpp','.hpp','.json'):shutil.copyfile(path,snapshot/path.name)
start=time.monotonic();best=execute_route(base).final_gamestate.age;rows=[]
if cube:
    command=[str(work/'native_quantity_cube'),str(seedfile),str(args.seconds),str(args.quantity_cube_minimum),str(args.width),str(args.quantity_start or 0),str(args.quantity_end if args.quantity_end is not None else 2**64-1),str(work/f'{args.name}.stop'),'0']
elif quantity_range:
    command=[str(work/'native_quantity_range'),str(seedfile),str(args.seconds),str(args.quantity_order),str(args.width),str(args.quantity_start or 0),str(args.quantity_end if args.quantity_end is not None else 2**64-1),str(work/f'{args.name}.stop'),'0',str(int(args.quantity_deletions))]
elif args.quantity_order:
    command=[str(work/'native_quantity_scan'),str(seedfile),str(args.seconds),str(args.quantity_order),str(args.width),str(work/f'{args.name}.stop'),str(int(args.partition_age_bound))]
else:
    command=[str(work/'native_anneal'),str(seedfile),str(args.seconds),str(args.seed),str(args.width),str(args.max_size),str(args.tmax),str(args.tmin),str(args.cycle),str(args.errand_bias),str(args.action_bias),str(int(args.expand)),str(int(args.blocks)),str(int(args.canonical_partition)),str(int(args.canonical_partials)),str(int(args.lock_upgrades)),str(args.restart_best),str(args.cache_size),str(args.trials),str(work/f'{args.name}.stop'),str(int(args.aggregate_partition))]
binary=snapshot/Path(command[0]).name;shutil.copy2(command[0],binary);command[0]=str(binary)
binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()
process=subprocess.Popen(command,stdout=subprocess.PIPE,text=True)
(work/f'{args.name}.pid').write_text(str(process.pid))
for line in process.stdout:
    row=json.loads(line)
    if 'route' in row:
        plan=replace(base,name=args.name,algorithm='experimental_native_quantity_scan' if args.quantity_order or cube else 'experimental_native_partition_search',
                     errands=tuple(unpack_actions(e) for e in row['route']),beam_width=None,errand_search_width=None,
                     ruler_scale=None,ruler_route=None,beam_max_expansions=None,
                     price_horizon_multiplier=None,errand_queue_depth=None,
                     max_errand_actions=16,max_errand_size=args.max_size,errand_state_width=args.width)
        result=execute_route(plan)
        if abs(result.final_gamestate.age-row['finish'])>1e-7:
            process.terminate();raise AssertionError((result.final_gamestate.age,row))
        row['python_finish']=result.final_gamestate.age;row['replay_verified']=True
        if result.final_gamestate.age<=best+1e-8:
            best=result.final_gamestate.age;plan=replace(plan,errands=action_errands(result))
            temporary=work/f'{args.name}.pending.route';write_route(temporary,plan,comment='Native order/partition search; every improvement validated with Python replay.',overwrite=True);temporary.replace(work/f'{args.name}.route')
    rows.append(row)
    with (work/f'{args.name}.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
    print(json.dumps(row),flush=True)
code=process.wait()
if code:raise SystemExit(code)
summary=dict(name=args.name,finish=best,elapsed=time.monotonic()-start,parameters=vars(args),binary=str(binary),binary_sha256=binary_sha256,last=rows[-1],route=str(work/f'{args.name}.route'))
(work/f'{args.name}.json').write_text(json.dumps(summary,indent=2)+'\n')

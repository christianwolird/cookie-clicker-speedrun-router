"""Replay and record a native policy-improvement run from the initial state."""
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
from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT/'src'))
from ccsr.routes import RoutePlan, write_route, execute_route
from ccsr.config import load_route_profile, load_player_profile, load_errand_profile, create_initial_gamestate
from native_bridge import unpack_actions, pack_state

p=argparse.ArgumentParser();p.add_argument('name');p.add_argument('--seconds',type=float,default=120)
p.add_argument('--options-json',default='{}');args=p.parse_args();work=WORK;work.mkdir(parents=True,exist_ok=True)
lease=(work/f'{args.name}.lock').open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
snapshot=work/'snapshots'/args.name;snapshot.mkdir(parents=True,exist_ok=True)
for path in Path(__file__).parent.iterdir():
    if path.suffix in ('.py','.cpp','.hpp','.json'):shutil.copyfile(path,snapshot/path.name)
profile=load_route_profile('million-250cps');player=load_player_profile(profile.player_profile);shop=load_errand_profile(profile.errand_profile)
initial=create_initial_gamestate(profile,player,errand_profile=shop);pack_state(initial)
if profile.target!=1_000_000 or not profile.upgrades_enabled or any(initial.building_counts.values()) or initial.purchased_upgrades or any((initial.age,initial.bank,initial.lifetime_cookies,initial.handmade_cookies)):
    raise ValueError('Native policy requires the one-million goal and an empty initial state with upgrades enabled')
base=RoutePlan(name=args.name,source='this codebase',goal=profile.goal,route_profile=profile.name,
               player_profile=player.name,version=profile.version,target=profile.target,click_rate=player.click_rate,
               initial_state=player.initial_state,algorithm='experimental_policy_greedy',upgrades_enabled=True,
               for_quickster=False,errands=(),errand_delay=player.errand_delay,action_delay=player.action_delay,
               errand_profile=shop.name,bulk_size=shop.bulk_size,selling_allowed=shop.selling_allowed,
               achievement_curve=profile.achievement_curve)
options=json.loads(args.options_json);cmd=[str(work/'native_policy'),'--seconds',str(args.seconds),'--stop-file',str(work/f'{args.name}.stop')]
binary=snapshot/'native_policy';shutil.copy2(work/'native_policy',binary);cmd[0]=str(binary)
binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest()
for key,value in options.items():cmd+=['--'+key,str(value)]
start=time.monotonic();rows=[]
process=subprocess.Popen(cmd,stdout=subprocess.PIPE,text=True)
for line in process.stdout:
    row=json.loads(line)
    if 'route' in row:
        plan=replace(base,name=args.name,algorithm='experimental_policy_greedy',
                     errands=tuple(unpack_actions(e) for e in row['route']),beam_width=None,
                     errand_search_width=options.get('inner',800),errand_queue_depth=options.get('pops',2000),
                     max_errand_actions=12,price_horizon_multiplier=None,ruler_scale=None,
                     ruler_route=None,beam_max_expansions=None)
        result=execute_route(plan);row['python_finish']=result.final_gamestate.age
        if abs(row['python_finish']-row['finish'])>1e-7:process.terminate();raise AssertionError(row)
        pending=work/f'{args.name}.pending.route';write_route(pending,plan,comment='Greedy policy improvement from the initial state; independently replayed.',overwrite=True)
        pending.replace(work/f'{args.name}.route');row['replay_verified']=True
    rows.append(row);print(json.dumps(row),flush=True)
    with (work/f'{args.name}.jsonl').open('a') as log:log.write(json.dumps(row)+'\n')
code=process.wait()
if code:raise SystemExit(code)
(work/f'{args.name}.json').write_text(json.dumps(dict(name=args.name,finish=rows[-1]['python_finish'],elapsed=time.monotonic()-start,options=options,binary=str(binary),binary_sha256=binary_sha256,last=rows[-1]),indent=2)+'\n')

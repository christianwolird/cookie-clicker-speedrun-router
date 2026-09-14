"""Run and record reproducible generator/beam variants on trained 250 CPS."""
import argparse
from dataclasses import asdict, replace
import json
from pathlib import Path
import shutil
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src'))
from ccsr.config import load_route_profile,load_player_profile,load_errand_profile,create_initial_gamestate
from ccsr.routes import RoutePlan,action_errands,execute_route,load_route,write_route
from generator_variants import Options,generate_neighbors
from beam_variants import SearchOptions,find_route
from experiment_paths import WORK

PRESETS={
    'baseline':Options(),
    'no_stop':Options(early_stop=False),
    'bonus10':Options(early_stop=False,distinct_results=True,upgrade_bonus=.1),
    'bonus20':Options(early_stop=False,distinct_results=True,upgrade_bonus=.2),
    'diverse':Options(early_stop=False,distinct_results=True,diverse_queue=2,diverse_results=2),
    'reserved':Options(early_stop=False,distinct_results=True,all_evaluated=True,seed_reserve=8),
    'balanced':Options(early_stop=False,distinct_results=True,all_evaluated=True,diverse_queue=2,diverse_results=2,expansion_balance=.05,seed_reserve=8),
    'balanced_bonus10':Options(early_stop=False,distinct_results=True,all_evaluated=True,diverse_queue=2,diverse_results=2,expansion_balance=.05,seed_reserve=8,upgrade_bonus=.1),
}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('name')
    parser.add_argument('--work',default=str(WORK))
    parser.add_argument('--variant',choices=PRESETS,default='baseline')
    parser.add_argument('--ruler',default='/tmp/ccsr-trained-12h-20260914/incumbent_start.route')
    parser.add_argument('--seconds',type=float,default=120)
    parser.add_argument('--width',type=int,default=20);parser.add_argument('--inner-width',type=int,default=40)
    parser.add_argument('--queue',type=int,default=100);parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--order',type=float,default=1.01);parser.add_argument('--prune',type=float,default=.94)
    parser.add_argument('--slack',type=float,default=0);parser.add_argument('--horizon',type=float,default=16)
    parser.add_argument('--heap-limit',type=int,default=100000)
    parser.add_argument('--no-prefix-seeds',action='store_true');parser.add_argument('--no-cap',action='store_true')
    parser.add_argument('--greedy',action='store_true');parser.add_argument('--options-json')
    args=parser.parse_args();work=Path(args.work);work.mkdir(exist_ok=True,parents=True)
    profile=load_route_profile('million-250cps');player=load_player_profile(profile.player_profile)
    shop=load_errand_profile(profile.errand_profile);initial=create_initial_gamestate(profile,player,errand_profile=shop)
    go=PRESETS[args.variant]
    if args.options_json: go=replace(go,**json.loads(args.options_json))
    so=SearchOptions(seconds=args.seconds,width=args.width,inner_width=args.inner_width,queue_expansions=args.queue,
                     horizon=args.horizon,workers=args.workers,order_scale=args.order,prune_scale=args.prune,
                     prune_slack=args.slack,seed_prefixes=not args.no_prefix_seeds,handmade_cap=not args.no_cap,
                     heap_limit=args.heap_limit)
    snapshot=work/f'{args.name}_ruler.route';shutil.copyfile(args.ruler,snapshot)
    ruler=execute_route(load_route(snapshot))
    plan=RoutePlan(name=args.name,source='this codebase',goal=profile.goal,route_profile=profile.name,
        achievement_curve=profile.achievement_curve,player_profile=player.name,version=profile.version,
        target=profile.target,click_rate=player.click_rate,initial_state=player.initial_state,
        algorithm='experimental_greedy' if args.greedy else 'experimental_beam',upgrades_enabled=profile.upgrades_enabled,
        for_quickster=False,errands=(),errand_delay=player.errand_delay,action_delay=player.action_delay,
        errand_profile=shop.name,bulk_size=shop.bulk_size,selling_allowed=shop.selling_allowed,
        max_errand_actions=so.max_actions,price_horizon_multiplier=args.horizon or None,errand_queue_depth=args.queue,
        beam_width=args.width,errand_search_width=args.inner_width,ruler_scale=args.prune,ruler_route=str(snapshot),beam_max_expansions=so.max_expansions)
    start=time.monotonic();improvements=[]
    def save_candidate(finish,errands):
        candidate=replace(plan,errands=action_errands(SimpleNamespace(errands=errands)))
        replay=execute_route(candidate)
        assert abs(replay.final_gamestate.age-finish.age)<1e-8
        temp=work/f'{args.name}.pending.route';write_route(temp,candidate,overwrite=True)
        temp.replace(work/f'{args.name}.route')
    def improved(finish,errands):
        save_candidate(finish,errands)
        row=dict(event='improvement',elapsed=time.monotonic()-start,finish=finish.age)
        improvements.append(row);print(json.dumps(row),flush=True)
    print(json.dumps(dict(event='start',name=args.name,ruler=ruler.final_gamestate.age,generator=asdict(go),search=asdict(so))),flush=True)
    if args.greedy:
        state=initial;errands=[]
        for _ in range(200):
            ns=generate_neighbors(state,profile.target,width=args.width,search_width=args.inner_width,
                queue_expansions=args.queue,price_horizon_multiplier=args.horizon,max_errand_actions=so.max_actions,options=go)
            ns=[n for n in ns if n.gamestate.finish(profile.target).age<state.finish(profile.target).age]
            if not ns:break
            chosen=ns[0];errands.append(chosen.purchases);state=chosen.gamestate
        result=SimpleNamespace(final_gamestate=state.finish(profile.target),errands=tuple(errands))
        stats={}
    else:
        result=find_route(initial,profile.target,ruler,so,go,on_improvement=improved,
                          on_progress=lambda p:print(json.dumps(dict(event='progress',**p)),flush=True))
        stats=asdict(result.search_stats)
    save_candidate(result.final_gamestate,result.errands)
    data=dict(name=args.name,finish=result.final_gamestate.age,ruler=ruler.final_gamestate.age,
              improved=result.final_gamestate.age<ruler.final_gamestate.age-1e-8,
              elapsed=time.monotonic()-start,stats=stats,generator=asdict(go),search=asdict(so),
              improvements=improvements,route=str(work/f'{args.name}.route'))
    (work/f'{args.name}.json').write_text(json.dumps(data,indent=2)+'\n')
    with (work/'search_results.jsonl').open('a') as f:f.write(json.dumps(data)+'\n')
    print(json.dumps(dict(event='complete',**data)),flush=True)

if __name__=='__main__':main()

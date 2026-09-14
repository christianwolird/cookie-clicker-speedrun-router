"""Replay changed route checkpoints and preserve the best trained result."""
import argparse,datetime,json,math,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,execute_route,write_route,action_errands
from dataclasses import replace
p=argparse.ArgumentParser();p.add_argument('--until',default='2026-09-14T14:24:58+00:00');args=p.parse_args()
end=datetime.datetime.fromisoformat(args.until).timestamp();work=Path('/tmp/ccsr-trained-12h-20260914')
seen={};scores={};best=math.inf;first=True
while time.time()<end:
    for path in work.glob('*.route'):
        if path.name.startswith('session_best') or '.pending.' in path.name:continue
        stamp=path.stat().st_mtime_ns
        if seen.get(str(path))==stamp:continue
        seen[str(path)]=stamp
        try:
            plan=load_route(path);state=initial_gamestate(plan)
            if plan.target!=1000000 or (state.version,state.click_rate,state.errand_delay,state.action_delay,state.bulk_size,state.selling_allowed,state.legacy_errands,state.achievement_curve)!=('2.031',250,.4,.1,10,False,False,None):continue
            result=execute_route(plan)
            scores[str(path)]=(result.final_gamestate.age,stamp,plan,result)
        except (ValueError,KeyError,AssertionError) as e:
            print(json.dumps(dict(event='replay_error',path=str(path),error=str(e))),flush=True)
    if scores:
        source,(score,stamp,plan,result)=min(scores.items(),key=lambda pair:(pair[1][0],pair[1][1],pair[0]))
        if score<best-1e-8:
            best=score;temporary=work/'session_best.pending.route'
            write_route(temporary,replace(plan,errands=action_errands(result)),comment='Best independently replay-verified trained250 result in this session.',overwrite=True)
            temporary.replace(work/'session_best.route')
            row=dict(event='initial_best' if first else 'improvement',finish=score,source=source,utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),errands=len(plan.errands),actions=sum(len(e) for e in plan.errands),verified=True)
            (work/'session_best.json').write_text(json.dumps(row,indent=2)+'\n')
            with (work/'session_best_history.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
            print(json.dumps(row),flush=True)
    first=False
    time.sleep(min(15,max(0,end-time.time())))
print(json.dumps(dict(event='complete',finish=best,checked_files=len(seen))),flush=True)

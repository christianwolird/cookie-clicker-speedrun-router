"""Publish the verified global checkpoint in the native seed format.

This process never writes session_best.route or its metadata; track_best.py
remains the sole owner of that checkpoint.
"""
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import sys
import time
from experiment_paths import ROOT, WORK
sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route, execute_route
from native_bridge import pack_actions, pack_state

work=WORK;lease=(work/'incumbent_publisher.lock').open('a');fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
deadline=datetime(2026,9,14,14,24,58,tzinfo=timezone.utc);seen=None;best=float('inf')
while datetime.now(timezone.utc)<deadline and not (work/'incumbent_publisher.stop').exists():
    path=work/'session_best.route';stamp=path.stat().st_mtime_ns
    if stamp!=seen:
        plan=load_route(path);result=execute_route(plan);pack_state(result.initial_gamestate)
        if plan.target!=1_000_000:raise ValueError('Shared native ruler must target one million')
        finish=result.final_gamestate.age
        if finish<best-1e-8:
            text=str(len(plan.errands))+'\n'+'\n'.join(str(len(e))+' '+' '.join(map(str,pack_actions(e))) for e in plan.errands)+'\n'
            pending=work/'shared_incumbent.pending.seed';pending.write_text(text);pending.replace(work/'shared_incumbent.seed')
            best=finish;print(json.dumps(dict(event='published',finish=finish,utc=datetime.now(timezone.utc).isoformat())),flush=True)
        seen=stamp
    time.sleep(2)

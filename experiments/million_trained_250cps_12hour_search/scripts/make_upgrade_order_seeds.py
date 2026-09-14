"""Repartition moves, swaps and omissions of incumbent upgrades."""
from dataclasses import replace
import json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,write_route,execute_route
from native_bridge import partition_actions
work=Path('/tmp/ccsr-trained-12h-20260914');base=load_route(work/'session_best.route')
flat=tuple(a for e in base.errands for a in e);candidates={flat}
positions=[i for i,a in enumerate(flat) if a.operation=='upgrade']
for i in positions:
    remainder=flat[:i]+flat[i+1:];candidates.add(remainder)
    for j in range(len(remainder)+1):candidates.add(remainder[:j]+(flat[i],)+remainder[j:])
    for j in positions:
        a=list(flat);a[i],a[j]=a[j],a[i];candidates.add(tuple(a))
families={}
for actions in candidates:
    errands,score=partition_actions(actions,width=4,max_size=16)
    if score>212:continue
    order=tuple(a.item for e in errands for a in e if a.operation=='upgrade')
    if order in families and families[order][0]<=score:continue
    plan=replace(base,errands=errands,algorithm='experimental_upgrade_order_seed',beam_width=None,
                 errand_search_width=None,ruler_scale=None,ruler_route=None,beam_max_expansions=None,
                 price_horizon_multiplier=None,errand_queue_depth=None,max_errand_size=16,errand_state_width=4)
    actual=execute_route(plan).final_gamestate.age;assert abs(actual-score)<1e-7
    families[order]=(actual,plan)
directory=work/'upgrade_order_seeds';directory.mkdir(exist_ok=True);rows=[]
for i,(order,(score,plan)) in enumerate(sorted(families.items(),key=lambda row:(row[1][0],row[0]))):
    name=f'upgrade_order_seed_{i:03d}';path=directory/f'{name}.route'
    write_route(path,replace(plan,name=name),comment='Replayed seed for a separate fixed-upgrade-order refinement.',overwrite=True)
    rows.append(dict(name=name,path=str(path),finish=score,upgrades=order))
(work/'upgrade_order_seeds.json').write_text(json.dumps(rows,indent=2)+'\n')
print(json.dumps(dict(candidates=len(candidates),families=len(families),rows=rows),indent=2))

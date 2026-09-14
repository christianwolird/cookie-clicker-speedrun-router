import json
from pathlib import Path
import sys
import time
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'src'))
from ccsr.routes import load_route,initial_gamestate,apply_errand
from generator_variants import Options,generate_neighbors
work=Path('/tmp/ccsr-trained-12h-20260914');plan=load_route(work/'local_v1.route');state=initial_gamestate(plan)
times={'stock_evaluator':0,'cached_evaluator':0};states=0
for actions in plan.errands:
    outputs=[]
    for name,fast in [('stock_evaluator',False),('cached_evaluator',True)]:
        start=time.monotonic()
        output=generate_neighbors(state,plan.target,width=40,search_width=80,queue_expansions=200,price_horizon_multiplier=16,
                                  options=Options(early_stop=False,distinct_results=True,all_evaluated=True,fast_evaluation=fast))
        times[name]+=time.monotonic()-start;outputs.append(output)
    assert [n.errand for n in outputs[0]]==[n.errand for n in outputs[1]]
    assert [n.purchases for n in outputs[0]]==[n.purchases for n in outputs[1]]
    state,_=apply_errand(state,actions);states+=1
result=dict(states=states,times=times,speedup=times['stock_evaluator']/times['cached_evaluator'])
(work/'benchmark_fast_generator.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

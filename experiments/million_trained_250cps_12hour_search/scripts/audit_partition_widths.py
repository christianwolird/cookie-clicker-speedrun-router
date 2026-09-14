"""Measure whether wider errand partition beams help mutated route sequences."""
import argparse
from dataclasses import replace
import json
import random
import sys
import time

from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT / 'src'))
from ccsr.routes import execute_route, load_route, write_route
from native_bridge import pack_actions, partition_actions, unpack_actions

p = argparse.ArgumentParser()
p.add_argument('--trials', type=int, default=20000)
args = p.parse_args()
paths = [WORK / name for name in ('session_best.route', 'native_local_cool.route',
                                  'policy_ensemble_bonuses.route',
                                  'policy_ensemble_wide.route')]
for name in ('long_root_forecast', 'long_wide_diverse', 'long_upgrade_bonus'):
    candidates = sorted((WORK / f'{name}_candidates').glob('*.route'))
    paths += candidates[::max(1, len(candidates)//20)]
plans = [load_route(path) for path in paths]
sequences = [[int(c) for e in plan.errands for c in pack_actions(e)] for plan in plans]
rng = random.Random(54381)
start = time.monotonic()
widths = (1, 4, 16, 32)
comparisons = {str(width): dict(better=0, worse=0, equal=0, max_gain=0) for width in widths if width != 4}
examples = []
competitive = 0
best = execute_route(plans[0]).final_gamestate.age
for trial in range(args.trials):
    codes = list(rng.choice(sequences))
    for _ in range(rng.randrange(1, 6)):
        i = rng.randrange(len(codes))
        operation = rng.randrange(5)
        if operation == 0:
            codes[i] = rng.randrange(5)*16 + rng.randrange(1, 11)
        elif operation == 1:
            j = rng.randrange(len(codes)); codes[i], codes[j] = codes[j], codes[i]
        elif operation == 2:
            codes.insert(i, rng.randrange(256, 272))
        elif operation == 3 and len(codes) > 1:
            del codes[i]
        else:
            codes.insert(i, rng.randrange(5)*16 + rng.randrange(1, 11))
    actions = unpack_actions(codes)
    results = {width: partition_actions(actions, width=width) for width in widths}
    reference = results[4][1]
    competitive += reference < 205
    for width, (route, score) in results.items():
        if width != 4:
            row = comparisons[str(width)]
            row['better' if score < reference-1e-8 else 'worse' if score > reference+1e-8 else 'equal'] += 1
            row['max_gain'] = max(row['max_gain'], reference-score)
            if score < reference-1e-8 and len(examples) < 20:
                plan = replace(plans[0], errands=route)
                assert abs(execute_route(plan).final_gamestate.age-score) < 1e-7
                examples.append(dict(trial=trial, width=width, reference=reference, finish=score, codes=codes))
        if score < best-1e-8:
            plan = replace(plans[0], name='partition_width_audit',
                           algorithm='experimental_native_partition_search', errands=route,
                           ruler_route=None, errand_state_width=width)
            assert abs(execute_route(plan).final_gamestate.age-score) < 1e-7
            best = score
            write_route(WORK / 'partition_width_audit.route', plan, overwrite=True)
    if (trial+1) % 2000 == 0:
        print(json.dumps(dict(trials=trial+1, elapsed=time.monotonic()-start, best=best)), flush=True)
result = dict(trials=args.trials, seeds=len(paths), widths=widths, finishes_below_205=competitive,
              elapsed=time.monotonic()-start,
              comparisons_to_width4=comparisons, examples=examples, best=best)
(WORK / 'partition_width_audit.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k != 'examples'}), flush=True)

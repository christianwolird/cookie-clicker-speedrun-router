"""Compare full generator outputs before avoiding futile queue insertions."""
import ctypes as C
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT / 'src'))
from ccsr.routes import load_route, initial_gamestate, apply_errand
from native_bridge import NativeOptions, NativeNeighbor, State, pack_state

OLD = '''evaluated.push_back({state,actions,raw,score,group});queue.insert({score,actions.size,index,group});++group_counts[group];'''
NEW = '''evaluated.push_back({state,actions,raw,score,group});
        QueueItem next{score,actions.size,index,group};
        // With no group quota, a new worst entry would immediately remove
        // itself. Keep it among evaluated results, but avoid the queue churn.
        if(!o.queue_diversity&&!queue.empty()&&int(queue.size())>=o.search_width&&
           !QueueLess{}(next,*queue.rbegin()))return index;
        queue.insert(next);++group_counts[group];'''

here = Path(__file__).resolve().parent
directory = WORK / 'queue_admission_comparison'
source = (here / 'native_generator.hpp').read_text().replace(NEW, OLD)
assert source.count(OLD) == 1
libraries = {}
for label in ('reference', 'early_reject'):
    folder = directory / label
    folder.mkdir(parents=True, exist_ok=True)
    for path in here.glob('*.hpp'):
        shutil.copyfile(path, folder / path.name)
    shutil.copyfile(here / 'native_library.cpp', folder / 'native_library.cpp')
    (folder / 'native_generator.hpp').write_text(source if label == 'reference' else source.replace(OLD, NEW))
    binary = folder / 'native_search.so'
    subprocess.run(['g++', '-std=c++17', '-O3', '-fPIC', '-shared',
                    str(folder / 'native_library.cpp'), '-o', str(binary)], check=True)
    library = C.CDLL(str(binary))
    library.native_generate.argtypes = [C.POINTER(State), C.POINTER(NativeOptions),
                                       C.POINTER(NativeNeighbor), C.c_int]
    library.native_generate.restype = C.c_int
    assert library.native_options_size() == C.sizeof(NativeOptions)
    assert library.native_neighbor_size() == C.sizeof(NativeNeighbor)
    libraries[label] = library

plan = load_route(WORK / 'session_best.route')
state = initial_gamestate(plan)
states = []
for actions in plan.errands:
    states.append(pack_state(state))
    state, _ = apply_errand(state, actions)
common = dict(width=160, search_width=400, pops=1000, max_actions=12,
              canonical=1, all_evaluated=1, anchor_all=4, upgrade_macros=1,
              future_upgrade_mask=32768, future_weight=1,
              canonical_partial=1, quantity_children=4)
variants = [('typical', {}), ('wide', dict(width=1200, search_width=1500, pops=5000)),
            ('action_children', dict(quantity_children=0)),
            ('forced_seeds', dict(expand_seeds=1)),
            ('balanced', dict(width=80, search_width=120, pops=300, expansion_balance=.01)),
            ('diverse', dict(queue_diversity=2))]
results = []
for name, changes in variants:
    values = dict(common, **changes)
    options = NativeOptions(**values)
    timings = {label: [] for label in libraries}
    expected = {}
    digest = hashlib.sha256()
    returned = 0
    for repeat in range(3):
        costs = dict.fromkeys(libraries, 0.0)
        labels = list(libraries) if repeat % 2 == 0 else list(reversed(libraries))
        for i, packed in enumerate(states):
            for label in labels:
                output = (NativeNeighbor * options.width)()
                start = time.process_time()
                count = libraries[label].native_generate(C.byref(packed), C.byref(options), output, len(output))
                costs[label] += time.process_time() - start
                data = C.string_at(output, count * C.sizeof(NativeNeighbor))
                if i not in expected:
                    expected[i] = data
                    digest.update(data)
                    returned += count
                assert data == expected[i], (name, label, repeat, i)
        for label in libraries:
            timings[label].append(costs[label])
    row = dict(name=name, states=len(states), neighbors=returned, options=values,
               cpu_seconds=timings, output_sha256=digest.hexdigest(), identical=True)
    results.append(row)
    (WORK / 'queue_admission_results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(row), flush=True)

"""Check parent-link reconstruction against the copied-route implementation."""
import ctypes as C
from dataclasses import replace
import json
import random
from pathlib import Path
import subprocess
import sys

from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT / 'src'))
from native_bridge import NativeErrand, pack_actions, unpack_actions
from ccsr.routes import execute_route, load_route

here = Path(__file__).resolve().parent
directory = WORK / 'partition_parent_comparison'
libraries = []
for label in ('reference', 'parents'):
    folder = directory / label
    source = (here / 'native_library.cpp').read_text() + '''
extern "C" int native_partition_extended(const std::uint16_t*actions,int count,int width,int max_size,
    int expand,int canonical,int partial,int aggregate,NativeErrand*out,double*score){
    auto solution=partition(std::vector<std::uint16_t>(actions,actions+count),width,max_size,expand,canonical,partial,0,aggregate);
    *score=solution.score;int i=0;
    for(const auto&a:solution.route){std::copy(a.data.begin(),a.data.end(),out[i].actions);out[i++].action_count=a.size;}
    return i;
}
'''
    (folder / 'native_library.cpp').write_text(source)
    binary = folder / 'native_search.so'
    subprocess.run(['g++', '-std=c++17', '-O3', '-fPIC', '-shared',
                    str(folder / 'native_library.cpp'), '-o', str(binary)], check=True)
    lib = C.CDLL(str(binary))
    lib.native_partition_extended.argtypes = [C.POINTER(C.c_uint16)] + [C.c_int]*7 + [C.POINTER(NativeErrand), C.POINTER(C.c_double)]
    lib.native_partition_extended.restype = C.c_int
    libraries.append(lib)

paths = [WORK / 'session_best.route', WORK / 'optimized_recipe_greedy.route',
         WORK / 'native_local_cool.route', ROOT / 'routes/million-250cps/generated_beam.route']
bases = [load_route(path) for path in paths]
sequences = [[int(code) for e in base.errands for code in pack_actions(e)] for base in bases]
rng = random.Random(22139)
replayed = 0
for trial in range(1200):
    actions = list(rng.choice(sequences))
    for _ in range(rng.randrange(1, 8)):
        i = rng.randrange(len(actions))
        mode = rng.randrange(4)
        if mode == 0:
            actions[i] = rng.randrange(5)*16 + rng.randrange(1, 11)
        elif mode == 1:
            j = rng.randrange(len(actions)); actions[i], actions[j] = actions[j], actions[i]
        elif mode == 2:
            actions.insert(i, rng.randrange(256, 272))
        elif len(actions) > 1:
            del actions[i]
    width = rng.choice((1, 4, 8, 16))
    expand = trial % 8 == 0
    aggregate = trial % 3 == 0
    canonical = trial % 4 == 0
    partial = trial % 5 == 0
    max_size = 128 if expand else 64 if aggregate else rng.choice((4, 8, 16))
    codes = (C.c_uint16*len(actions))(*actions)
    results = []
    for lib in libraries:
        output = (NativeErrand*1024)(); score = C.c_double()
        count = lib.native_partition_extended(codes, len(actions), width, max_size,
                                             expand, canonical, partial, aggregate, output, C.byref(score))
        route = tuple(tuple(e.actions[:e.action_count]) for e in output[:count])
        results.append((score.value, route))
    assert results[0] == results[1], (trial, results)
    if trial % 4 == 0:
        score, route = results[1]
        plan = replace(bases[0], errands=tuple(unpack_actions(e) for e in route))
        assert abs(execute_route(plan).final_gamestate.age-score) < 1e-7
        replayed += 1
result = dict(sequences=1200, python_replays=replayed, identical=True)
(WORK / 'partition_parent_verification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))

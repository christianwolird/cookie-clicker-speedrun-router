"""Benchmark cached upgrade factors against every represented upgrade mask."""
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
from native_bridge import NativeOptions, NativeNeighbor, State, pack_state
from ccsr.routes import load_route, initial_gamestate, apply_errand

NEW_RATES = '''struct RateFactors {
    double cursor=1,finger=0,production=1,mouse=0;
    std::array<double,NB> building;unsigned synergies=0;
};
static_assert(NU<=16,"Upgrade factor table is restricted to the small native catalog");
inline const auto RATE_FACTORS=[](){
    std::array<RateFactors,1u<<NU> table{};
    for(unsigned mask=0;mask<table.size();++mask){auto&f=table[mask];f.building.fill(1);
        for(int i=0;i<NU;++i)if(mask&(1u<<i)){const auto&u=UPGRADES[i];
            f.cursor*=u.cursor;f.finger+=u.finger;f.production*=u.production;f.mouse+=u.mouse;
            if(u.building>=0)f.building[u.building]*=2;
            if(u.synergy>=0){f.building[1]*=2;f.synergies|=1u<<u.synergy;}
        }
    }
    return table;
}();
inline Rates rates(const NativeState&s) {
    const auto&f=RATE_FACTORS[s.upgrades&((1u<<NU)-1)];auto mult=f.building;
    // The represented synergy upgrades follow all ordinary building upgrades.
    // Preserve each floating-point operation and the production summation order.
    for(int b=2;b<NB;++b)if(f.synergies&(1u<<b))mult[b]*=1+s.buildings[1]*.01/(b-1);
    int noncursor=0;for(int i=1;i<NB;++i)noncursor+=s.buildings[i];
    double automatic=s.buildings[0]*(BASE_CPS[0]*f.cursor+f.finger*noncursor)*mult[0];
    for(int i=1;i<NB;++i)automatic+=s.buildings[i]*BASE_CPS[i]*mult[i];
    automatic*=f.production;
    return {automatic,250*(f.cursor+f.finger*noncursor+f.mouse*automatic)};
}
'''


def main():
    here = Path(__file__).resolve().parent
    directory = WORK / 'rate_factor_comparison'
    libraries = {}
    core = (here / 'native_core.hpp').read_text()
    start = core.index('inline Rates rates(')
    end = core.index('inline double finish(', start)
    original = core[start:end]
    if 'RATE_FACTORS' in core:
        raise SystemExit('This comparison must start from the original rate loop')
    for label in ('reference', 'factors'):
        folder = directory / label
        folder.mkdir(parents=True, exist_ok=True)
        for path in here.glob('*.hpp'):
            shutil.copyfile(path, folder / path.name)
        changed = core if label == 'reference' else core[:start] + NEW_RATES + core[end:]
        (folder / 'native_core.hpp').write_text(changed)
        source = (here / 'native_library.cpp').read_text()
        source += '\n' + original.replace('inline Rates rates(', 'inline Rates reference_rates(')
        source += '''
extern "C" int native_rate_factor_audit(){
    std::uint64_t x=871337;
    for(unsigned mask=0;mask<(1u<<NU);++mask)for(int pattern=0;pattern<32;++pattern){
        NativeState s{};s.upgrades=mask;
        for(int b=0;b<NB;++b){x=x*6364136223846793005ULL+1442695040888963407ULL;s.buildings[b]=int(x%120)-10;}
        auto expected=reference_rates(s),actual=rates(s);
        if(std::memcmp(&expected,&actual,sizeof(Rates)))return 0;
    }
    return 1;
}
'''
        (folder / 'native_library.cpp').write_text(source)
        binary = folder / 'native_search.so'
        subprocess.run(['g++', '-std=c++17', '-O3', '-fPIC', '-shared',
                        str(folder / 'native_library.cpp'), '-o', str(binary)], check=True)
        lib = C.CDLL(str(binary))
        lib.native_generate.argtypes = [C.POINTER(State), C.POINTER(NativeOptions),
                                       C.POINTER(NativeNeighbor), C.c_int]
        lib.native_generate.restype = C.c_int
        assert lib.native_rate_factor_audit() == 1, label
        libraries[label] = lib
    plan = load_route(WORK / 'session_best.route')
    states = []
    state = initial_gamestate(plan)
    for actions in plan.errands:
        states.append(pack_state(state))
        state, _ = apply_errand(state, actions)
    common = dict(width=160, search_width=400, pops=1000, max_actions=12,
                  canonical=1, all_evaluated=1, anchor_all=4, upgrade_macros=1,
                  future_upgrade_mask=32768, future_weight=1,
                  canonical_partial=1, quantity_children=4)
    variants = [('typical', {}), ('wide', dict(width=1200, search_width=1500, pops=5000)),
                ('action_children', dict(quantity_children=0)),
                ('diverse', dict(queue_diversity=2)),
                ('inventory_forecast', dict(future_counts=[10, 20, 10, 3, 0])),
                ('negative_virtual_counts', dict(future_counts=[-1, 0, 0, 0, 0])),
                ('no_forecast', dict(future_weight=0)),
                ('mixed_bonus', dict(future_weight=.5, upgrade_bonus=.1))]
    rows = []
    for name, changes in variants:
        fields = dict(common, **changes)
        if 'future_counts' in fields:
            fields['future_counts'] = (C.c_int * 5)(*fields['future_counts'])
        options = NativeOptions(**fields)
        costs = {label: [] for label in libraries}
        expected = {}
        digest = hashlib.sha256()
        for repeat in range(3):
            timing = dict.fromkeys(libraries, 0.0)
            for i, packed in enumerate(states):
                for label in list(libraries)[::1 if repeat % 2 == 0 else -1]:
                    output = (NativeNeighbor * options.width)()
                    before = time.process_time()
                    count = libraries[label].native_generate(C.byref(packed), C.byref(options), output, len(output))
                    timing[label] += time.process_time() - before
                    data = C.string_at(output, count * C.sizeof(NativeNeighbor))
                    if i not in expected:
                        expected[i] = data
                        digest.update(data)
                    assert data == expected[i], (name, label, repeat, i)
            for label, value in timing.items():
                costs[label].append(value)
        row = dict(name=name, cpu_seconds=costs, sha256=digest.hexdigest(), identical=True)
        rows.append(row)
        print(json.dumps(row), flush=True)
    (WORK / 'rate_factor_benchmark.json').write_text(json.dumps(dict(
        masks=65536, states_per_mask=32, rows=rows), indent=2) + '\n')


if __name__ == '__main__':
    main()

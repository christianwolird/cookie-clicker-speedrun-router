"""Isolate exact price and source-rate caching in copied native prototypes."""
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

PRICE_OLD = '''    std::uint64_t result=0;for(int k=0;k<q;++k)result+=PRICES[i][owned+k];return result;'''
PRICE_NEW = '''    return CUMULATIVE_PRICES[i][owned+q]-CUMULATIVE_PRICES[i][owned];'''
PRICE_TABLE = '''inline constexpr auto CUMULATIVE_PRICES=[](){
    std::array<std::array<std::uint64_t,NP+1>,NB> result{};
    for(int i=0;i<NB;++i)for(int j=0;j<NP;++j)result[i][j+1]=result[i][j]+PRICES[i][j];
    return result;
}();
'''
PREPARE = '''    const auto source_rates=rates(a);const double source_total=source_rates.total();
    bool future_buildings=std::any_of(o.future_counts.begin(),o.future_counts.end(),[](int q){return q>0;});
    bool changed_inventory=std::any_of(o.future_counts.begin(),o.future_counts.end(),[](int q){return q!=0;});
    NativeState future_source=a;for(int j=0;j<NB;++j)future_source.buildings[j]+=o.future_counts[j];
    double future_total=changed_inventory?rates(future_source).total():source_total;
    future_source.upgrades|=o.future_upgrade_mask;
    double masked_total=o.future_upgrade_mask?rates(future_source).total():future_total;
    auto score_after=[&](const NativeState&b,double before){
        double after=rates(b).total();if(after<=before)return std::numeric_limits<double>::infinity();
        return (b.age-a.age)*after/(after-before);
    };
'''
SCORE_OLD = '''        double raw=age_score(a,state),score=future_score(a,state,o);'''
SCORE_NEW = '''        double raw=score_after(state,source_total),score=raw;
        if(o.future_weight&&(o.future_upgrade_mask||future_buildings)){
            NativeState forecast=state;for(int j=0;j<NB;++j)forecast.buildings[j]+=o.future_counts[j];
            double potential=changed_inventory?std::min(raw,score_after(forecast,future_total)):raw;
            if(o.future_upgrade_mask){forecast.upgrades|=o.future_upgrade_mask;potential=std::min(potential,score_after(forecast,masked_total));}
            score=std::isfinite(raw)?(1-o.future_weight)*raw+o.future_weight*potential:potential;
        }'''

here = Path(__file__).resolve().parent
directory = WORK / 'native_hot_path_comparison'
libraries = {}
for label, prices, rates_cached in [('reference', False, False), ('prices', True, False),
                                    ('source_rates', False, True), ('both', True, True)]:
    folder = directory / label
    folder.mkdir(parents=True, exist_ok=True)
    for path in here.glob('*.hpp'):
        shutil.copyfile(path, folder / path.name)
    shutil.copyfile(here / 'native_library.cpp', folder / 'native_library.cpp')
    core = (folder / 'native_core.hpp').read_text()
    generator = (folder / 'native_generator.hpp').read_text()
    core = core.replace(PRICE_TABLE, '').replace(PRICE_NEW, PRICE_OLD)
    core = core.replace('double horizon=16,const Rates*cached_rates=nullptr) {', 'double horizon=16) {')
    core = core.replace('auto r=cached_rates?*cached_rates:rates(a);double pause=', 'auto r=rates(a);double pause=')
    generator = generator.replace(PREPARE, '').replace(SCORE_NEW, SCORE_OLD)
    generator = generator.replace('actions.size,state,target,o.horizon,&source_rates)', 'actions.size,state,target,o.horizon)')
    assert PRICE_OLD in core and SCORE_OLD in generator
    if prices:
        core = core.replace('inline std::uint64_t building_price(', PRICE_TABLE + 'inline std::uint64_t building_price(')
        core = core.replace(PRICE_OLD, PRICE_NEW)
    if rates_cached:
        core = core.replace('double horizon=16) {', 'double horizon=16,const Rates*cached_rates=nullptr) {')
        core = core.replace('auto r=rates(a);double pause=', 'auto r=cached_rates?*cached_rates:rates(a);double pause=')
        generator = generator.replace('    auto add=[&](Actions actions)->int {', PREPARE + '    auto add=[&](Actions actions)->int {')
        generator = generator.replace('actions.size,state,target,o.horizon)', 'actions.size,state,target,o.horizon,&source_rates)')
        generator = generator.replace(SCORE_OLD, SCORE_NEW)
    (folder / 'native_core.hpp').write_text(core)
    (folder / 'native_generator.hpp').write_text(generator)
    # Independently check every represented price interval, including invalid bounds.
    library_source = (folder / 'native_library.cpp').read_text()
    library_source += '''
extern "C" int native_price_audit(){
    for(int i=-1;i<=NB;++i)for(int owned=-1;owned<=NP;++owned)for(int q=0;q<=NP+1;++q){
        std::uint64_t reference=UINT64_MAX/2;
        if(i>=0&&i<NB&&owned>=0&&q>=1&&owned+q<=NP){reference=0;for(int j=0;j<q;++j)reference+=PRICES[i][owned+j];}
        if(building_price(i,owned,q)!=reference)return 0;
    }return 1;
}
'''
    (folder / 'native_library.cpp').write_text(library_source)
    binary = folder / 'native_search.so'
    subprocess.run(['g++', '-std=c++17', '-O3', '-fPIC', '-shared',
                    str(folder / 'native_library.cpp'), '-o', str(binary)], check=True)
    library = C.CDLL(str(binary))
    library.native_generate.argtypes = [C.POINTER(State), C.POINTER(NativeOptions),
                                       C.POINTER(NativeNeighbor), C.c_int]
    library.native_generate.restype = C.c_int
    assert library.native_options_size() == C.sizeof(NativeOptions)
    assert library.native_neighbor_size() == C.sizeof(NativeNeighbor)
    assert library.native_price_audit() == 1
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
            ('diverse', dict(queue_diversity=2)),
            ('inventory_forecast', dict(future_counts=[10, 20, 10, 3, 0])),
            ('inventory_only', dict(future_counts=[10, 20, 10, 3, 0], future_upgrade_mask=0)),
            ('negative_virtual_counts', dict(future_counts=[-1, 0, 0, 0, 0])),
            ('no_forecast', dict(future_weight=0)),
            ('mixed_weight_bonus', dict(future_weight=.5, upgrade_bonus=.1))]
results = []
for name, changes in variants:
    values = dict(common, **changes)
    fields = dict(values)
    if 'future_counts' in fields:
        fields['future_counts'] = (C.c_int * 5)(*fields['future_counts'])
    options = NativeOptions(**fields)
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
    (WORK / 'native_hot_path_results.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(row), flush=True)

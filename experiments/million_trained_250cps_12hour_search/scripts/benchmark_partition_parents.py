"""Compare full-route copying with parent links in the partition dynamic program."""
import json
from pathlib import Path
import resource
import shutil
import subprocess
import time

from experiment_paths import WORK

REPLACEMENTS = [
    ('struct Plan {NativeState state{};Route route;};',
     'struct Plan {NativeState state{};int parent_position=-1,parent_index=-1;Actions incoming;};'),
    ('states[0].push_back({initial,{}});', 'states[0].push_back({initial,-1,-1,{}});'),
    ('Solution best{finish(initial),{}};', 'double best_score=finish(initial);int best_position=0;'),
    ('Plan plan{child,ancestor.route};plan.route.push_back(executed);',
     'Plan plan{child,start,int(&ancestor-states[start].data()),executed};'),
    ('if(!candidates.empty()&&finish_here(candidates[0].state)<best.score){best={finish_here(candidates[0].state),candidates[0].route};}',
     'if(!candidates.empty()&&finish_here(candidates[0].state)<best_score){best_score=finish_here(candidates[0].state);best_position=end;}'),
    ('    return best;\n}', '''    Route route;int position=best_position,index=0;
    while(position){const auto&plan=states[position][index];route.push_back(plan.incoming);
        position=plan.parent_position;index=plan.parent_index;
    }
    std::reverse(route.begin(),route.end());return {best_score,std::move(route)};
}'''),
]


def main():
    here = Path(__file__).resolve().parent
    directory = WORK / 'partition_parent_comparison'
    original = (here / 'native_partition.hpp').read_text()
    if 'parent_position=-1,parent_index=-1' in original:
        for before, after in reversed(REPLACEMENTS):
            assert original.count(after) == 1, after
            original = original.replace(after, before)
    for label in ('reference', 'parents'):
        folder = directory / label
        folder.mkdir(parents=True, exist_ok=True)
        for path in here.glob('*.hpp'):
            shutil.copyfile(path, folder / path.name)
        (folder / 'native_partition.hpp').write_text(original)
        if label == 'parents':
            path = folder / 'native_partition.hpp'
            code = path.read_text()
            for before, after in REPLACEMENTS:
                assert code.count(before) == 1, before
                code = code.replace(before, after)
            path.write_text(code)
        for binary in ('native_anneal', 'native_quantity_range'):
            shutil.copyfile(here / f'{binary}.cpp', folder / f'{binary}.cpp')
            subprocess.run(['g++', '-std=c++17', '-O3', '-pthread',
                            str(folder / f'{binary}.cpp'), '-o', str(folder / binary)], check=True)
    trials = [
        ('default', 40000, 4, 16, 0, 0),
        ('wide', 20000, 16, 16, 0, 0),
        ('aggregate_flat', 20000, 4, 64, 0, 1),
        ('aggregate_units', 5000, 4, 128, 1, 1),
    ]
    rows = []
    for name, count, width, max_size, expand, aggregate in trials:
        runs = []
        for label in ('reference', 'parents'):
            command = [str(directory / label / 'native_anneal'),
                       str(WORK / 'quantity_scan_best_5.seed'), '900', '22019',
                       str(width), str(max_size), '.8', '.001', '20000', '0', '0',
                       str(expand), '1', '0', '0', '0', '.25', '100000', str(count),
                       str(WORK / 'unused_parent_benchmark.stop'), str(aggregate)]
            before = resource.getrusage(resource.RUSAGE_CHILDREN)
            started = time.monotonic()
            result = subprocess.run(command, capture_output=True, text=True, check=True)
            after = resource.getrusage(resource.RUSAGE_CHILDREN)
            events = [json.loads(line) for line in result.stdout.splitlines()]
            runs.append(dict(label=label, events=events, elapsed=time.monotonic()-started,
                             cpu_seconds=after.ru_utime+after.ru_stime-before.ru_utime-before.ru_stime))
        def normalized(run):
            return [{k: v for k, v in event.items() if k != 'elapsed'} for event in run['events']
                    if event['event'] != 'progress']
        assert normalized(runs[0]) == normalized(runs[1]), name
        row = dict(name=name, identical=True, runs=runs)
        rows.append(row)
        print(json.dumps(dict(name=name, cpu=[r['cpu_seconds'] for r in runs], identical=True)), flush=True)
    audit = []
    for label in ('reference', 'parents'):
        result = subprocess.run([str(directory / label / 'native_quantity_range'),
                                 str(WORK / 'quantity_scan_best_5.seed'), '900', '5', '4',
                                 '300000000', '300010000', str(WORK / 'unused_parent_benchmark.stop'), '1'],
                                capture_output=True, text=True, check=True)
        audit.append([json.loads(line) for line in result.stdout.splitlines()])
    normalized = lambda events: [{k: v for k, v in event.items() if k != 'elapsed'} for event in events]
    assert normalized(audit[0]) == normalized(audit[1])
    (WORK / 'partition_parent_benchmark.json').write_text(json.dumps(dict(rows=rows, range_audit=audit), indent=2)+'\n')
    print(json.dumps(dict(range_identical=True)), flush=True)


if __name__ == '__main__':
    main()

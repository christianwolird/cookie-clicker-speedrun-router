"""Combine checked ranges without confusing vectors, routes, or global optimality."""
import argparse
import json
import math

from experiment_paths import WORK

p = argparse.ArgumentParser()
p.add_argument('--require-complete', action='store_true')
args = p.parse_args()

def read(name):
    path = WORK / (name+'.json')
    return json.loads(path.read_text()) if path.exists() else None

source_row = json.loads((WORK / 'quantity_scan_best_5.jsonl').read_text().splitlines()[0])
source = [code for errand in source_row['route'] for code in errand]
building_actions = sum(code < 256 for code in source)
baseline = source_row['finish']

def checked(name, expected_order, deletion=False):
    row = read(name)
    if row is None:
        return None
    initial = json.loads((WORK / (name+'.jsonl')).read_text().splitlines()[0])
    assert [code for errand in initial['route'] for code in errand] == source, name
    parameters = row['parameters']
    assert parameters['width'] == 4 and parameters['quantity_order'] == expected_order, name
    assert bool(parameters.get('quantity_deletions', False)) == deletion, name
    return row

def covered(ranges, total):
    cursor = 0
    amount = 0
    for start, end in sorted(ranges):
        assert 0 <= start <= end <= total, (start, end, total)
        amount += max(0, end-max(cursor, start))
        cursor = max(cursor, end)
    return amount

rows = []
best = baseline
for deletion in (False, True):
    for order in range(1, 6):
        count = math.comb(building_actions, order) * (10**order-9**order if deletion else 9**order)
        ranges = []
        if not deletion and order == 5:
            ledger = read('quantity_coverage_ledger')
            for part in ledger['completed']:
                trial = checked(part['name'], order)
                assert trial is not None
                last = trial['last']
                assert last['tried'] == part['end']-part['start'], part
                if 'next_index' in last:
                    assert last['next_index'] == part['end'], part
                else:
                    assert last['passes'] == 1 and part['start'] == 0, part
                ranges.append((part['start'], part['end']))
                best = min(best, trial['finish'])
        else:
            if deletion:
                names = ['deletion_smoke_order3'] if order == 3 else \
                        ['deletion_order5_a', 'deletion_order5_b'] if order == 5 else [f'deletion_order{order}']
                if order == 5:
                    names += [path.stem for path in sorted(WORK.glob('deletion_order5_resume*.json'))]
            else:
                names = [f'quantity_certificate_order{order}' if order <= 2 else f'quantity_scan_best_{order}']
            for name in names:
                trial = checked(name, order, deletion)
                if trial is None:
                    continue
                last = trial['last']
                if 'range_start' in last:
                    start, end = last['range_start'], last['next_index']
                    assert last['tried'] == end-start, name
                else:
                    assert last['passes'] == 1 and last['tried'] == count and last['improvements'] == 0, name
                    start, end = 0, count
                ranges.append((start, end))
                best = min(best, trial['finish'])
        amount = covered(ranges, count)
        rows.append(dict(deletion_only=deletion, order=order, expected=count,
                         covered=amount, complete=amount == count, ranges=ranges))
report = dict(source_codes=source, building_actions=building_actions, partition_width=4,
              max_errand_actions=16, action_order_fixed=True, baseline=baseline, best=best,
              expected_changed_vectors=sum(row['expected'] for row in rows),
              examined_changed_vectors=sum(row['covered'] for row in rows),
              complete=all(row['complete'] for row in rows), neighborhoods=rows,
              limitation='Distinct quantity vectors, not necessarily distinct routes; finite partition width and fixed action order remain restrictions.')
(WORK / 'combined_neighborhood_coverage.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({key: value for key, value in report.items() if key not in ('source_codes', 'neighborhoods')}))
if args.require_complete and not report['complete']:
    raise SystemExit('Neighborhood coverage is incomplete')

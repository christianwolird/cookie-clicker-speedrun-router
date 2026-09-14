"""Check disjoint coverage of the sparse and dense quantity neighborhoods."""
import json
from experiment_paths import WORK

sparse = json.loads((WORK / 'combined_neighborhood_coverage.json').read_text())
dense = json.loads((WORK / 'quantity_cube_suite.json').read_text())
assert sparse['complete'] and dense['complete']
source = sparse['source_codes']
coefficients = [1]
for code in source:
    if code >= 256:
        continue
    quantity = code % 16
    alternatives = min(10, quantity+1)-max(0, quantity-1)
    next_coefficients = [0]*(len(coefficients)+1)
    for changed, count in enumerate(coefficients):
        next_coefficients[changed] += count
        next_coefficients[changed+1] += count*alternatives
    coefficients = next_coefficients
expected = sum(coefficients[6:])
assert dense['total'] == expected
cursor = 0
best = sparse['best']
for row in sorted(dense['trials'], key=lambda row: row['last']['range_start']):
    initial = json.loads((WORK / (row['name']+'.jsonl')).read_text().splitlines()[0])
    assert [code for e in initial['route'] for code in e] == source
    parameters = row['parameters']
    assert parameters['quantity_cube_minimum'] == 6 and parameters['width'] == 4
    assert not parameters['quantity_order'] and not parameters['quantity_deletions']
    last = row['last']
    assert last['range_start'] == cursor and last['range_finished']
    assert last['range_end'] == last['next_index']
    assert last['tried'] == last['next_index']-cursor
    cursor = last['next_index']
    best = min(best, row['finish'])
assert cursor == expected
report = dict(complete=True, source_codes=source, quantity_coefficients=coefficients,
              sparse_changed_vectors=sparse['examined_changed_vectors'],
              dense_changed_vectors=expected,
              total_changed_vectors=sparse['examined_changed_vectors']+expected,
              source_sequences_identical=True, neighborhoods_disjoint=True,
              partition_width=4, best=best,
              limitation='Fixed action order and bounded partition width; distinct vectors can produce identical routes. No global optimality certificate.')
(WORK / 'extended_neighborhood_coverage.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_codes', 'quantity_coefficients')}))

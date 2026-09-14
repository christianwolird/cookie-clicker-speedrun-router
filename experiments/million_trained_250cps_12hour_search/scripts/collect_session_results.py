"""Preserve compact measurements and route snapshots outside temporary storage."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from experiment_paths import ROOT, WORK, DOCS, FILE_RELOCATION
sys.path.insert(0, str(ROOT / 'src'))
from ccsr.routes import execute_route, load_route

p = argparse.ArgumentParser()
p.add_argument('--final', action='store_true')
args = p.parse_args()
now = datetime.now(timezone.utc)
if args.final and now < datetime.fromisoformat('2026-09-14T14:24:58+00:00'):
    p.error('The twelve-hour session has not finished yet')

def read(name):
    path = WORK / name
    return json.loads(path.read_text()) if path.exists() else None

def route_snapshot(path):
    plan = load_route(path)
    result = execute_route(plan)
    return dict(finish=result.final_gamestate.age, errands=len(plan.errands),
                actions=sum(map(len, plan.errands)),
                final_inventory={name:count for name,count in result.final_gamestate.building_counts.items() if count},
                final_upgrades=sorted(result.final_gamestate.purchased_upgrades),
                final_bank=result.final_gamestate.bank, text=path.read_text())

def trial(row):
    result = {key: row[key] for key in ('name', 'initial', 'finish', 'direct_finish',
                                       'elapsed', 'cpu_seconds', 'options', 'binary_sha256') if key in row}
    result['statistics'] = {key: row['last'][key] for key in
                            ('expanded', 'generated', 'termination', 'tried', 'computed',
                             'cache_hits', 'improvements', 'external_adoptions', 'range_finished', 'exhausted', 'passes',
                             'range_start', 'range_end', 'next_index') if key in row.get('last', {})}
    if 'parameters' in row:
        result['parameters'] = {key:value for key,value in row['parameters'].items() if key != 'options_json'}
    if 'direct_finish' not in result and row.get('options', {}).get('report-generated'):
        log = WORK / (row['name']+'.jsonl')
        if log.exists():
            events = [json.loads(line) for line in log.read_text().splitlines()]
            direct = next((event for event in reversed(events) if event.get('event') == 'generated_best'), None)
            if direct:
                result['direct_finish'] = direct.get('python_finish', direct['finish'])
                result['direct_finish_evidence'] = 'Recorded generated_best event; older summary omitted this field.'
    return result

baseline = route_snapshot(WORK / 'canonical_before_curation/generated_beam.route')
best = route_snapshot(WORK / 'session_best.route')
best_source = WORK / 'session_best.route'
for name in ('delivery_best_refined.route', 'validated_recipe_refined.route', 'optimized_recipe_refined.route', 'recipe_best_from_scratch.route'):
    candidate_path = WORK / name
    if candidate_path.exists():
        candidate = route_snapshot(candidate_path)
        if abs(candidate['finish']-best['finish']) < 1e-8:
            best, best_source = candidate, candidate_path
            break
report = dict(
    status='complete' if args.final else 'running',
    started_utc='2026-09-14T02:24:58+00:00', planned_finish_utc='2026-09-14T14:24:58+00:00',
    snapshot_utc=now.isoformat(),
    model=dict(route_profile='million-250cps', goal='one_million', target=1000000,
               version='2.031', player_profile='trained_250_cps', click_rate=250,
               errand_delay=.4, action_delay=.1, bulk_size=10, selling_allowed=False),
    baseline=baseline, best=best, improvement_seconds=baseline['finish']-best['finish'],
    best_snapshot_source=str(best_source),
    incumbent_record=read('session_best.json'),
    tracked_improvements=[json.loads(line) for line in
        (WORK / 'session_best_history.jsonl').read_text().splitlines()]
        if (WORK / 'session_best_history.jsonl').exists() else [],
    excluded_timing_prefixes=read('retired_trial_prefixes.json'),
    scope='Best found in the stated continuous simulator; no global optimality certificate.',
)
report['recipes'] = {}
for key, filename in [('fast', 'fast_recipe.json'), ('best', 'optimized_best_recipe_reproduction.json'),
                      ('validated_best', 'validated_best_recipe_reproduction.json'),
                      ('delivery_fast', 'delivery_fast_recipe.json'), ('delivery_best', 'delivery_best_recipe.json')]:
    data = read(filename)
    if data:
        report['recipes'][key] = dict(elapsed=data['elapsed'], greedy=trial(data['greedy']),
                                      refined=trial(data['refined']))
report['forecast_comparison'] = [trial(row) for row in (read('parameter_c_results.json') or [])]
report['prefetch_fixed_expansions'] = [trial(row) for row in (read('prefetch_comparison.json') or [])]
report['prefetch_fixed_time'] = [trial(row) for row in (read('prefetch_timed_comparison.json') or [])]
report['prefetch_refinement'] = [trial(row) for row in (read('prefetch_refinement.json') or [])]
report['crossover_pilots'] = [trial(row) for row in (read('crossover_pilot_results.json') or [])]
canonical_manifest = read('canonical_neighborhood_manifest.json')
if canonical_manifest:
    canonical_results = read('canonical_neighborhood_results.json')
    canonical_rows = canonical_results['results'] if canonical_results else \
        (read('canonical_neighborhood_0.json') or []) + (read('canonical_neighborhood_1.json') or [])
    report['canonical_representative_checks'] = dict(manifest=canonical_manifest,
        finished_utc=canonical_results['finished_utc'] if canonical_results else None,
        trials=[trial(row) for row in canonical_rows],
        scope='Alternate equivalent starting representation; these neighborhoods overlap the earlier scans and are not added to their distinct-vector count.')
canonical_lower = read('canonical_lower_orders_results.json')
if canonical_lower:
    report['canonical_lower_orders'] = dict(
        finished_utc=canonical_lower['finished_utc'], source_text=canonical_lower['source_text'],
        trials=[trial(row) for row in canonical_lower['results']])
report['worker_batch_benchmark'] = read('worker_batches_benchmark.json')
report['delay_rank_reversal'] = read('route_delay_rank_reversal.json')
report['near_tie_delay_sensitivity'] = read('near_tie_delay_sensitivity.json')
report['long_beams'] = [trial(row) for name in ('long_root_forecast', 'long_wide_diverse',
                                               'long_upgrade_bonus', 'long_inventory_restricted')
                        if (row := read(name+'.json'))]
report['policy_ensembles'] = []
for shard in (0, 1):
    for row in read(f'policy_ensemble_suite_{shard}.json') or []:
        report['policy_ensembles'].append(dict(name=row['name'],
            **{key: trial(row[key]) for key in ('greedy', 'locked', 'open')}))
report['quantity_coverage'] = read('quantity_coverage_ledger.json')
deletion_names = ['deletion_smoke_order3', 'deletion_order1', 'deletion_order2',
                  'deletion_order4', 'deletion_order5_a', 'deletion_order5_b']
deletion_names += [path.stem for path in sorted(WORK.glob('deletion_order5_resume*.json'))]
report['deletion_scans'] = [trial(row) for name in deletion_names
                           if (row := read(name+'.json'))]
report['quantity_source_alignment'] = read('positive_quantity_source_alignment.json')
report['combined_neighborhood_coverage'] = read('combined_neighborhood_coverage.json')
report['extended_neighborhood_coverage'] = read('extended_neighborhood_coverage.json')
report['canonical_coverage_verification'] = read('canonical_coverage_verification.json')
cube = read('quantity_cube_suite.json')
if cube:
    report['dense_quantity_neighborhood'] = {k:v for k,v in cube.items() if k != 'trials'}
    report['dense_quantity_neighborhood']['trials'] = [trial(row) for row in cube['trials']]
report['partition_parent_verification'] = read('partition_parent_verification.json')
report['partition_width_audit'] = read('partition_width_audit.json')
report['validated_build'] = read('session_final_build_manifest.json')
report['delivery_build'] = read('delivery_build_manifest.json')
report['canonical_exports'] = read('canonical_export_manifest.json')
parent = read('partition_parent_benchmark.json')
if parent:
    report['partition_parent_performance'] = [dict(name=row['name'], identical=row['identical'],
        cpu_seconds={run['label']: run['cpu_seconds'] for run in row['runs']}) for row in parent['rows']]
factors = read('rate_factor_benchmark.json')
if factors:
    report['upgrade_factor_prototype'] = dict(promoted=False, masks=factors['masks'],
                                              states_per_mask=factors['states_per_mask'], rows=factors['rows'])
archive = read('final_archive_results.json')
if archive:
    runs = [run for row in archive['results'] for run in row['refinements']]
    manifest = read('final_archive_manifest.json')
    report['final_archive_refinement'] = dict(observed=manifest['observed'], unique=manifest['unique'],
        previously_refined=manifest['previously_refined'], seconds_per_refinement=manifest['seconds_per_refinement'],
        finished_utc=archive['finished_utc'], runs=len(runs), trials=sum(row['tried'] for row in runs),
        finish=min((row['finish'] for row in runs), default=None))
crossovers = read('final_crossover_results.json')
if crossovers:
    report['final_crossovers'] = dict(metadata=crossovers['metadata'],
        finished_utc=crossovers['finished_utc'], runs=[trial(row) for row in crossovers['results']])
report['file_relocation'] = FILE_RELOCATION
output = DOCS / 'trained-250cps-search-results.json'
output.write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(dict(path=str(output), status=report['status'], finish=best['finish'],
                      completed_long_beams=len(report['long_beams']))))

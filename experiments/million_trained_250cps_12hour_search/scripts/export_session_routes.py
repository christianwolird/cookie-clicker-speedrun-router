"""Curate replay-verified session winners and preserve their portable provenance."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import sys

from experiment_paths import ROOT, WORK

sys.path.insert(0, str(ROOT / 'src'))
from ccsr.config import load_route_profile
from ccsr.routes import execute_route, load_route, write_route
from ccsr.routes.catalog import matches_profile, profile_details

p = argparse.ArgumentParser()
p.add_argument('--greedy', type=Path, required=True)
p.add_argument('--beam', type=Path, required=True)
p.add_argument('--best', type=Path, default=WORK / 'session_best.route')
p.add_argument('--write', action='store_true', help='Otherwise only prepare the export manifest')
args = p.parse_args()
profile = profile_details(load_route_profile('million-250cps'))


def inspect(path):
    plan = load_route(path)
    if not matches_profile(plan, profile):
        raise ValueError(f'Route does not use the requested trained profile: {path}')
    result = execute_route(plan)
    trial_name = path.stem.removesuffix('_generated')
    summary_path = path.with_name(trial_name + '.json')
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else None
    source_path = path.with_name(trial_name + '_source.route')
    direct_event = None
    if path.stem.endswith('_generated'):
        for line in path.with_name(trial_name+'.jsonl').read_text().splitlines():
            event = json.loads(line)
            if event.get('event') == 'generated_best':
                direct_event = event
        if direct_event is None or abs(direct_event['finish']-result.final_gamestate.age) > 1e-7:
            raise ValueError(f'Missing matching direct-generation evidence: {path}')
    return plan, dict(
        source_file=str(path), finish=result.final_gamestate.age,
        errands=len(plan.errands), actions=sum(map(len, plan.errands)),
        original_route_text=path.read_text(), trial=summary,
        direct_generation_event=direct_event,
        supplied_route_text=source_path.read_text() if source_path.exists() else None,
    )


greedy, greedy_info = inspect(args.greedy)
beam, beam_info = inspect(args.beam)
best, best_info = inspect(args.best)
if 'policy' not in greedy.algorithm and 'greedy' not in greedy.algorithm:
    raise ValueError('The greedy export must originate from a greedy/policy search')
if not args.beam.stem.endswith('_generated') or 'beam' not in beam.algorithm:
    raise ValueError('Use a directly generated beam completion, not a supplied ruler fallback')
if best_info['finish'] > beam_info['finish'] + 1e-7:
    raise ValueError('The session best is slower than the supplied beam route')

exports = [('generated_greedy.route', greedy, greedy_info),
           ('generated_beam.route', beam, beam_info)]
if best_info['finish'] < beam_info['finish'] - 1e-7:
    exports.append(('generated_refined.route', best, best_info))
destination = ROOT / 'routes/million-250cps'
manifest = dict(profile='million-250cps', written=args.write, routes=[])
manifest['original_snapshots'] = [dict(name=path.name, text=path.read_text())
                                  for path in sorted((WORK / 'canonical_before_curation').glob('*.route'))]
for filename, plan, info in exports:
    plan = replace(plan, name=f'million-250cps {filename.removesuffix(".route")}',
                   ruler_route=None)
    # .route has a fixed metadata schema. Keep the complete experimental options
    # and actual supplied ruler snapshot in the durable JSON instead of a /tmp link.
    comment = ('Twelve-hour search, 2026-09-14; replay and generation provenance: '
               'experiments/million_trained_250cps_12hour_search/docs/trained-250cps-search-results.json; reproduction: '
               'experiments/million_trained_250cps_12hour_search/README.md.')
    output = destination / filename
    if args.write:
        write_route(output, plan, comment=comment, overwrite=True)
        if abs(execute_route(load_route(output)).final_gamestate.age - info['finish']) > 1e-8:
            raise AssertionError(f'Export replay changed: {output}')
    manifest['routes'].append(dict(path=str(output.relative_to(ROOT)), **info))

obsolete = ('generated_beam_quick.route', 'generated_beam_refined.route')
if len(exports) == 2:
    obsolete += ('generated_refined.route',)
manifest['removed'] = []
for filename in obsolete:
    path = destination / filename
    if path.exists():
        manifest['removed'].append(dict(path=str(path.relative_to(ROOT)), text=path.read_text()))
        if args.write:
            path.unlink()
(WORK / 'canonical_export_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps(dict(written=args.write, routes=[{k: row[k] for k in
      ('path', 'finish', 'errands', 'actions')} for row in manifest['routes']])))

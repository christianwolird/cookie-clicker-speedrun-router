"""Read experiment progress without controlling jobs or writing checkpoints."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from experiment_paths import WORK

p = argparse.ArgumentParser()
p.add_argument('names', nargs='*')
args = p.parse_args()
names = args.names or ['long_root_forecast', 'long_wide_diverse',
                       'long_upgrade_bonus', 'long_inventory_restricted',
                       'quantity_prefix_fast_5', 'quantity_tail_fast_5']
if not args.names:
    for suffix in ('bonuses', 'wide', 'outer_bonus', 'strong_rollout'):
        for refinement in ('', '_locked', '_open'):
            name = 'policy_ensemble_' + suffix + refinement
            if (WORK / (name + '.jsonl')).exists() and not (WORK / (name + '.json')).exists():
                names.append(name)
    for name in ('deletion_order4', 'deletion_order5_a', 'deletion_order5_b'):
        if (WORK / (name + '.jsonl')).exists() and not (WORK / (name + '.json')).exists():
            names.append(name)
best_path = WORK / 'session_best.json'
best = json.loads(best_path.read_text()) if best_path.exists() else {}
jobs = []
for name in names:
    path = WORK / (name + '.jsonl')
    if not path.exists():
        path = WORK / (name + '.log')
    if not path.exists():
        continue
    for line in reversed(path.read_text().splitlines()):
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        fields = ('event', 'finish', 'elapsed', 'expanded', 'generated',
                  'tried', 'nodes', 'queue', 'next_index', 'termination')
        jobs.append(dict(name=name, **{key: row[key] for key in fields if key in row}))
        break
memory = dict(line.split(':', 1) for line in Path('/proc/meminfo').read_text().splitlines())
archive = None
if (WORK / 'final_archive_manifest.json').exists():
    manifest = json.loads((WORK / 'final_archive_manifest.json').read_text())
    results = WORK / 'final_archive_results.jsonl'
    archive = dict(total=manifest['unique'], completed=len(results.read_text().splitlines()) if results.exists() else 0)
print(json.dumps(dict(utc=datetime.now(timezone.utc).isoformat(),
                     best=best.get('finish'), jobs=jobs, final_archive=archive,
                     available_memory_gib=int(memory['MemAvailable'].split()[0]) / 2**20,
                     free_disk_gib=shutil.disk_usage(WORK).free / 2**30)))

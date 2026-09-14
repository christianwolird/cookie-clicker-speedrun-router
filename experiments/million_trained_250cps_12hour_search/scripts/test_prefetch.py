"""Exercise bounded prefetch batches, compaction and replay."""
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT / 'src'))
from ccsr.routes import execute_route, load_route
from native_bridge import pack_actions, unpack_actions


class PrefetchTests(unittest.TestCase):
    def test_prefetch_compaction_replay_and_exact_expansion_cap(self):
        base = load_route(ROOT / 'routes/million-250cps/generated_beam.route')
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / 'seed'
            seed.write_text(str(len(base.errands))+'\n'+'\n'.join(
                str(len(e))+' '+' '.join(map(str, pack_actions(e))) for e in base.errands)+'\n')
            result = subprocess.run([str(WORK / 'native_beam'), '--seed', str(seed),
                '--seconds', '60', '--workers', '2', '--persistent-workers', '1',
                '--batch-size', '8', '--expansions', '37', '--width', '30', '--inner', '60',
                '--pops', '50', '--horizon', '0', '--order', '1', '--stage-balance', '1',
                '--compact', '1', '--nodes', '500', '--heap', '50', '--harvest', '8',
                '--target-rollout', '1', '--canonical-partials', '1', '--report-generated', '1'],
                check=True, capture_output=True, text=True, timeout=90)
            rows = [json.loads(line) for line in result.stdout.splitlines()]
            self.assertEqual(rows[-1]['expanded'], 37)
            self.assertEqual(rows[-1]['termination'], 'expansion_limit')
            self.assertGreater(rows[-1]['compactions'], 0)
            for row in rows:
                if 'route' in row:
                    route = replace(base, errands=tuple(unpack_actions(e) for e in row['route']))
                    self.assertAlmostEqual(execute_route(route).final_gamestate.age, row['finish'], places=7)

    def test_prefetch_cannot_silently_increase_worker_count(self):
        result = subprocess.run([str(WORK / 'native_beam'), '--seed', 'unused',
                                 '--workers', '2', '--batch-size', '8'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn('persistent worker pool', result.stderr)


if __name__ == '__main__':
    unittest.main()

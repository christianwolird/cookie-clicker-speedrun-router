"""Independent Cartesian enumeration for the dense quantity scanner."""
from dataclasses import replace
from itertools import product
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


class QuantityCubeTests(unittest.TestCase):
    def test_all_neighbors_match_cartesian_oracle(self):
        self.compare(0)

    def test_minimum_changes_ranges_and_resume_match_oracle(self):
        self.compare(2)

    def test_unreachable_minimum_is_empty(self):
        self.compare(32)

    def compare(self, minimum):
        base = load_route(ROOT / 'routes/million-250cps/generated_beam.route')
        base = replace(base, errands=base.errands[:8])
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / 'seed'
            seed.write_text(str(len(base.errands))+'\n'+'\n'.join(
                str(len(e))+' '+' '.join(map(str, pack_actions(e))) for e in base.errands)+'\n')

            def run(begin, end, seconds=60):
                result = subprocess.run([str(WORK / 'native_quantity_cube'), str(seed),
                    str(seconds), str(minimum), '4', str(begin), str(end), '', '1'],
                    check=True, text=True, capture_output=True)
                rows = [json.loads(line) for line in result.stdout.splitlines()]
                final = rows[-1]
                plan = replace(base, errands=tuple(unpack_actions(e) for e in final['route']))
                self.assertAlmostEqual(execute_route(plan).final_gamestate.age, final['finish'], places=7)
                return rows[0], final

            initial, whole = run(0, 2**64-1)
            flat = [code for e in initial['route'] for code in e]
            positions = [i for i, code in enumerate(flat) if code < 256]
            choices = [range(max(0, flat[i] % 16-1), min(10, flat[i] % 16+1)+1) for i in positions]
            hashes = []
            mask = 2**64-1
            for values in product(*choices):
                if sum(value != flat[i] % 16 for i, value in zip(positions, values)) < minimum:
                    continue
                candidate = list(flat)
                for i, value in zip(positions, values):
                    candidate[i] = flat[i] // 16*16 + value
                fingerprint = 1469598103934665603
                for code in candidate:
                    fingerprint = ((fingerprint ^ code)*1099511628211) & mask
                hashes.append(fingerprint ^ ((len(hashes)*0x9e3779b97f4a7c15) & mask))

            def fingerprint(begin, end):
                value = 0
                for item in hashes[begin:end]:
                    value ^= item
                return value

            total = len(hashes)
            self.assertEqual(whole['total_combinations'], total)
            self.assertEqual(whole['tried'], total)
            self.assertEqual(whole['fingerprint'], fingerprint(0, total))
            self.assertTrue(whole['range_finished'])
            cuts = sorted({0, min(17, total), total//2, total})
            for begin, end in zip(cuts, cuts[1:]):
                _, row = run(begin, end)
                self.assertEqual(row['next_index'], end)
                self.assertEqual(row['tried'], end-begin)
                self.assertEqual(row['fingerprint'], fingerprint(begin, end))
            if total:
                begin = min(17, total)
                _, interrupted = run(begin, total, .001)
                next_index = interrupted['next_index']
                self.assertEqual(interrupted['tried'], next_index-begin)
                self.assertEqual(interrupted['fingerprint'], fingerprint(begin, next_index))
                _, resumed = run(next_index, total)
                self.assertEqual(resumed['fingerprint'], fingerprint(next_index, total))
                self.assertTrue(resumed['range_finished'])


if __name__ == '__main__':
    unittest.main()

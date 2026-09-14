"""Check range indexing against independently sorted Cartesian products."""
from dataclasses import replace
from itertools import combinations, product
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from experiment_paths import ROOT, WORK
sys.path.insert(0, str(ROOT / 'src'))
from ccsr.routes import load_route, execute_route
from native_bridge import pack_actions, unpack_actions


class QuantityRangeTests(unittest.TestCase):
    def test_disjoint_ranges_and_resume_match_cartesian_oracle(self):
        self.compare_ranges(deletions=False)

    def test_deletion_ranges_and_resume_match_cartesian_oracle(self):
        self.compare_ranges(deletions=True)

    def compare_ranges(self, deletions):
        base = load_route(ROOT / 'routes/million-250cps/generated_beam.route')
        with tempfile.TemporaryDirectory() as directory:
            seed = Path(directory) / 'seed'
            seed.write_text(str(len(base.errands)) + '\n' + '\n'.join(
                str(len(e)) + ' ' + ' '.join(map(str, pack_actions(e)))
                for e in base.errands) + '\n')

            def run(begin, end, seconds=60):
                completed = subprocess.run([
                    str(WORK / 'native_quantity_range'), str(seed), str(seconds),
                    '2', '4', str(begin), str(end), '', '1', str(int(deletions))],
                    check=True, text=True, capture_output=True)
                rows = [json.loads(line) for line in completed.stdout.splitlines()]
                final = rows[-1]
                plan = replace(base, errands=tuple(unpack_actions(e) for e in final['route']))
                self.assertAlmostEqual(execute_route(plan).final_gamestate.age, final['finish'], places=7)
                return rows[0], final

            initial, whole = run(0, 2**64 - 1)
            flat = [code for errand in initial['route'] for code in errand]
            positions = [j for j, code in enumerate(flat) if code < 256]
            total = math.comb(len(positions), 2) * (19 if deletions else 81)
            self.assertEqual(whole['tried'], total)
            self.assertEqual(whole['next_index'], total)
            self.assertTrue(whole['range_finished'])
            choices = []
            for at in combinations(positions, 2):
                quantities = [[q for q in range(0 if deletions else 1, 11) if q != flat[j] % 16] for j in at]
                for values in product(*quantities):
                    if deletions and 0 not in values:
                        continue
                    key = tuple(value for pair in zip(at, values) for value in pair)
                    choices.append((key, at, values))
            choices.sort()
            mask = 2**64 - 1
            hashes = []
            for index, (_, at, values) in enumerate(choices):
                candidate = list(flat)
                for j, q in zip(at, values):
                    candidate[j] = (candidate[j] // 16) * 16 + q
                value = 1469598103934665603
                for code in candidate:
                    value = ((value ^ code) * 1099511628211) & mask
                hashes.append(value ^ ((index * 0x9e3779b97f4a7c15) & mask))

            def fingerprint(begin, end):
                result = 0
                for value in hashes[begin:end]:
                    result ^= value
                return result

            self.assertEqual(whole['fingerprint'], fingerprint(0, total))
            cuts = sorted({0, 1, min(137, total), total // 2, total})
            shards = []
            for begin, end in zip(cuts, cuts[1:]):
                _, row = run(begin, end)
                self.assertEqual(row['tried'], end - begin)
                self.assertEqual(row['next_index'], end)
                self.assertEqual(row['fingerprint'], fingerprint(begin, end))
                self.assertTrue(row['range_finished'])
                shards.append(row)
            self.assertAlmostEqual(min(r['finish'] for r in shards), whole['finish'], places=7)
            _, partial = run(137, total, seconds=.03)
            next_index = partial['next_index']
            self.assertEqual(partial['tried'], next_index - 137)
            self.assertEqual(partial['fingerprint'], fingerprint(137, next_index))
            _, resumed = run(next_index, total)
            self.assertEqual(resumed['fingerprint'], fingerprint(next_index, total))
            self.assertTrue(resumed['range_finished'])


if __name__ == '__main__':
    unittest.main()

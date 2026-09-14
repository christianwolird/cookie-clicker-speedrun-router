"""Validate the optional greedy-policy ensemble through independent replay."""
import json
import subprocess
import unittest
from dataclasses import replace

from experiment_paths import WORK
from native_bridge import unpack_actions
from ccsr.config import load_route_profile
from ccsr.routes import execute_route, load_route, use_route_profile


class PolicyEnsembleTests(unittest.TestCase):
    def run_policy(self, *extra):
        result = subprocess.run(
            [str(WORK / 'native_policy'), '--seconds', '60', '--pool', '20',
             '--inner', '40', '--pops', '60', '--rollout-width', '8',
             '--rollout-inner', '20', '--rollout-pops', '30', *extra],
            capture_output=True, text=True, timeout=90,
        )
        return result

    def test_default_and_duplicate_zero_are_identical(self):
        baseline = self.run_policy()
        explicit = self.run_policy('--rollout-bonuses', '0,0')
        self.assertEqual(baseline.returncode, 0, baseline.stderr)
        self.assertEqual(explicit.returncode, 0, explicit.stderr)
        def normalized(result):
            return [{k: v for k, v in json.loads(line).items() if k != 'elapsed'}
                    for line in result.stdout.splitlines()]
        self.assertEqual(normalized(baseline), normalized(explicit))

    def test_alternative_policies_replay(self):
        result = self.run_policy('--rollout-bonuses', '0,0.05,0.1')
        self.assertEqual(result.returncode, 0, result.stderr)
        from experiment_paths import ROOT
        base = use_route_profile(
            load_route(ROOT / 'routes/million-250cps/generated_greedy.route'),
            load_route_profile('million-250cps'),
        )
        finishes = []
        for line in result.stdout.splitlines():
            row = json.loads(line)
            if 'route' not in row:
                continue
            route = replace(base, errands=tuple(unpack_actions(e) for e in row['route']))
            actual = execute_route(route).final_gamestate.age
            self.assertAlmostEqual(actual, row['finish'], places=7)
            finishes.append(actual)
        self.assertGreater(len(finishes), 1)
        self.assertEqual(finishes, sorted(finishes, reverse=True))

    def test_invalid_bonus_lists_are_rejected(self):
        for value in ('', '-0.1', 'nan', '0.1invalid'):
            with self.subTest(value=value):
                self.assertNotEqual(self.run_policy('--rollout-bonuses', value).returncode, 0)


if __name__ == '__main__':
    unittest.main()

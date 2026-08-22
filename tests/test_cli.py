import subprocess
import sys
import unittest
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_make_route_category_and_cli_override(self):
        result = subprocess.run(
            [
                sys.executable,
                "make_route.py",
                "--category",
                "one_million",
                "--target",
                "1000",
                "--click-rate",
                "20",
                "--algorithm",
                "singleton_errands",
            ],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Click rate: 20.0", result.stdout)
        self.assertIn("Done!", result.stdout)

    def test_replay_route_verbose_table(self):
        route = (
            REPOSITORY
            / "routes/from_online/singletons/neverclick_neverclick_36champ.route"
        )
        result = subprocess.run(
            [sys.executable, "scripts/replay_route.py", route, "--verbose"],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Current CpS", result.stdout)
        self.assertIn("Done!", result.stdout)

    def test_fuzzy_astar_category_reports_search_stats(self):
        result = subprocess.run(
            [
                sys.executable,
                "make_route.py",
                "--category",
                "10k",
                "--target",
                "1000",
                "--errand-queue-depth",
                "20",
                "--astar-feelers",
                "3",
                "--astar-inner-search",
                "bounded_beam",
                "--astar-heuristic",
                "measuring_stick",
                "--astar-max-expansions",
                "100",
                "--astar-progress-interval",
                "0.000001",
            ],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Algorithm: fuzzy_astar", result.stdout)
        self.assertIn("A* inner search: bounded_beam", result.stdout)
        self.assertIn("A* heuristic: measuring_stick", result.stdout)
        self.assertIn("Search progress", result.stdout)
        self.assertIn("Search:", result.stdout)


if __name__ == "__main__":
    unittest.main()

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from tools.beam_search_router import _print_progress


REPOSITORY = Path(__file__).resolve().parents[1]


class CliTests(unittest.TestCase):
    def test_beam_progress_uses_compact_elapsed_time(self):
        progress = SimpleNamespace(
            elapsed_seconds=65.2,
            expanded=1,
            generated=2,
            relaxed=3,
            stale_skipped=4,
            queue_size=5,
            maximum_queue_size=6,
            best_finish_age=70,
            frontier=(),
        )
        output = io.StringIO()

        with redirect_stdout(output):
            _print_progress(progress)

        self.assertTrue(output.getvalue().startswith("Progress (1:05) "))

    def test_greedy_router_accepts_category_player_and_quickster(self):
        result = subprocess.run(
            [
                sys.executable,
                "tools/greedy_router.py",
                "--category",
                "10k",
                "--player",
                "casual",
                "--quickster",
            ],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Player: casual", result.stdout)
        self.assertIn("For Quickster: True", result.stdout)
        self.assertIn("Done!", result.stdout)

    def test_beam_router_uses_temporary_greedy_ruler(self):
        result = subprocess.run(
            [
                sys.executable,
                "tools/beam_search_router.py",
                "--category",
                "10k",
                "--beam-width",
                "3",
                "--max-expansions",
                "100",
            ],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("temporary greedy route", result.stdout)
        self.assertIn("Player: default_10_cps", result.stdout)
        self.assertIn("Ruler scale: 0.9", result.stdout)
        self.assertIn("Search:", result.stdout)

    def test_route_replayer_uses_stored_profile(self):
        route = (
            REPOSITORY
            / "routes/online/quickster_originals/neverclick_neverclick_36champ.route"
        )
        result = subprocess.run(
            [sys.executable, "tools/route_replayer.py", route],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("default_neverclick", result.stdout)
        self.assertIn("Done!", result.stdout)

    def test_errandifier_writes_human_route(self):
        route = (
            REPOSITORY
            / "routes/online/quickster_originals"
            / "one_million_fast_clicks_15_cps_dha.route"
        )
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "errandified.route"
            subprocess.run(
                [
                    sys.executable,
                    "tools/errandifier.py",
                    route,
                    output,
                    "--player",
                    "casual",
                ],
                cwd=REPOSITORY,
                check=True,
                capture_output=True,
                text=True,
            )
            contents = output.read_text()

        self.assertIn("player_profile = casual", contents)
        self.assertIn("errand_delay = 1.0", contents)


if __name__ == "__main__":
    unittest.main()

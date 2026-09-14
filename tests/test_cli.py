import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tools.beam_search_router import _print_progress
from tools import route_replayer
from ccsr.config import load_player_profile
from ccsr.routes import execute_route, load_route


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
                "--route-profile",
                "10k-10cps",
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
                "--route-profile",
                "10k-10cps",
                "--beam-width",
                "3",
                "--workers",
                "2",
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
            / "routes/neverclick-0cps/community_quickster_36champ.route"
        )
        result = subprocess.run(
            [sys.executable, "tools/route_replayer.py", route],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("neverclick", result.stdout)
        self.assertIn("Done!", result.stdout)

    def test_realtime_replay_schedules_errands_and_completion_without_drift(self):
        source = load_route(
            REPOSITORY
            / "routes/million-15cps/community_errandified_dha.route"
        )
        for player_name, empty in ((None, False), ("casual", False), (None, True)):
            with self.subTest(player=player_name, empty=empty):
                plan = replace(source, errands=() if empty else source.errands[:2])
                player = load_player_profile(player_name) if player_name else None
                expected = execute_route(plan, player=player)
                now = 100.0
                printed = []

                def fake_sleep(seconds):
                    nonlocal now
                    self.assertGreater(seconds, 0)
                    now += seconds

                def slow_load(path):
                    nonlocal now
                    now += 0.25
                    return plan

                def record_errand(errand):
                    nonlocal now
                    printed.append((now - 100.0, errand))
                    now += 0.125  # Printing must not shift later deadlines.

                def record_done(state, target):
                    printed.append((now - 100.0, "done"))
                    self.assertEqual(target, plan.target)

                args = ["example.route", "--realtime"]
                if player_name:
                    args.extend(("--player", player_name))
                with (
                    patch.object(route_replayer, "monotonic", side_effect=lambda: now),
                    patch.object(route_replayer, "sleep", side_effect=fake_sleep),
                    patch.object(route_replayer, "load_route", side_effect=slow_load),
                    patch.object(route_replayer, "LiveRouteTable") as table_class,
                    redirect_stdout(io.StringIO()),
                ):
                    table = table_class.return_value
                    table.print_errand.side_effect = record_errand
                    table.print_done.side_effect = record_done
                    route_replayer.main(args)

                self.assertEqual(len(printed), len(expected.errands) + 1)
                for (elapsed, errand), expected_errand in zip(printed, expected.errands):
                    self.assertAlmostEqual(elapsed, expected_errand[0].age)
                    self.assertEqual(errand, expected_errand)
                self.assertAlmostEqual(printed[-1][0], expected.final_gamestate.age)
                self.assertEqual(printed[-1][1], "done")

    def test_realtime_replay_prints_overdue_events_without_sleeping(self):
        with (
            patch.object(route_replayer, "monotonic", return_value=105),
            patch.object(route_replayer, "sleep") as sleep,
        ):
            route_replayer._wait_until(100, 3)
            route_replayer._wait_until(100, 5)
        sleep.assert_not_called()

    def test_verbose_replay_does_not_wait_without_realtime(self):
        route = (
            REPOSITORY
            / "routes/neverclick-0cps/community_quickster_36champ.route"
        )
        output = io.StringIO()
        with patch.object(route_replayer, "sleep") as sleep, redirect_stdout(output):
            route_replayer.main([str(route), "--verbose"])
        sleep.assert_not_called()
        self.assertIn("Errand cookies", output.getvalue())
        self.assertIn("Done!", output.getvalue())

    def test_errandifier_writes_human_route(self):
        route = (
            REPOSITORY
            / "routes/million-15cps/community_quickster_dha.route"
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

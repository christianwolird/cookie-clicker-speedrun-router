import tempfile
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from make_route import RouteResult, find_route, load_category, print_result, save_route
from scripts.extract_public_routes import extract_routes
from scripts.replay_route import execute_route, load_route, main
from src.game import Game


REPOSITORY = Path(__file__).resolve().parent.parent


class RouteFileTests(unittest.TestCase):
    def test_all_online_routes_extract_parse_and_execute(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = extract_routes(
                REPOSITORY / "routes" / "dha_spreadsheets", directory
            )

            self.assertEqual(len(paths), 9)
            self.assertEqual(len({path.name for path in paths}), 9)
            self.assertFalse(any("_row" in path.stem for path in paths))
            for path in paths:
                with self.subTest(path=path.name):
                    plan = load_route(path)
                    result = execute_route(plan)
                    self.assertEqual(result.game.cookies, plan.target)
                    self.assertTrue(result.purchases)

    def test_normalized_route_is_plain_readable_text(self):
        with tempfile.TemporaryDirectory() as directory:
            path = extract_routes(
                REPOSITORY / "routes" / "dha_spreadsheets", directory
            )[0]
            contents = path.read_text()

            self.assertIn("target = ", contents)
            self.assertRegex(contents, r"(?m)^source = dha spreadsheet: .+ row \d+$")
            self.assertIn("version = ", contents)
            self.assertNotIn("profile = ", contents)
            self.assertRegex(contents, r"(?m)^buy \S+")
            self.assertNotIn("Cursor_up", contents)
            self.assertNotIn("Super_up", contents)

    def test_extraction_rejects_a_real_filename_collision(self):
        route_text = "\n".join(["Start", *(["Cursor"] * 6)])
        rows = [
            (2, {"B": route_text, "C": "same author", "D": "Neverclick"}),
            (3, {"B": route_text, "C": "same author", "D": "Neverclick"}),
        ]

        with (
            tempfile.TemporaryDirectory() as source_directory,
            tempfile.TemporaryDirectory() as output_directory,
        ):
            workbook = Path(source_directory) / "Neverclick routes.xlsx"
            workbook.touch()
            with patch(
                "scripts.extract_public_routes._route_rows",
                return_value=rows,
            ):
                with self.assertRaisesRegex(ValueError, "filename collision"):
                    extract_routes(source_directory, output_directory)

    def test_replay_route_cli_uses_standard_output(self):
        route = next(
            (REPOSITORY / "routes" / "from_online").glob("neverclick_*.route")
        )

        result = subprocess.run(
            [
                sys.executable,
                REPOSITORY / "scripts" / "replay_route.py",
                route,
                "--verbose",
            ],
            cwd=REPOSITORY,
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Target: 1,000,000 cookies", result.stdout)
        self.assertIn("Cookies produced", result.stdout)
        self.assertRegex(result.stdout, r"Final time: \d+:\d{2}\.\d$")

    def test_cli_version_overrides_route_metadata(self):
        route = next(
            (REPOSITORY / "routes" / "from_online").glob("one_million_*.route")
        )
        plan = load_route(route)
        result = RouteResult(Game("1.0466"), ())

        with (
            patch("scripts.replay_route.load_route", return_value=plan),
            patch(
                "scripts.replay_route.execute_route",
                return_value=result,
            ) as execute,
            patch("scripts.replay_route.print_result"),
            redirect_stdout(StringIO()),
        ):
            main([str(route), "--version", "1.0466"])

        execute.assert_called_once_with(plan, "1.0466", on_purchase=None)

    def test_saved_generated_route_is_replay_source_of_truth(self):
        settings = load_category("one_million")
        settings["target"] = 1_000
        game = Game(settings["version"])
        game.clickrate = settings["click_rate"]
        game.purchase_delay = settings["purchase_delay"]
        game.price_cutoff_multiplier = settings["price_cutoff_multiplier"]
        game.allow_upgrades = settings["allow_upgrades"]
        generated = find_route(game, settings["target"])

        with tempfile.TemporaryDirectory() as directory:
            path = save_route(
                Path(directory) / "generated.route",
                settings,
                generated,
            )
            contents = path.read_text()
            plan = load_route(path)
            replayed = execute_route(plan)

        self.assertIn("source = this codebase", contents)
        self.assertEqual(
            [purchase.route_action() for purchase in generated.purchases],
            [purchase.route_action() for purchase in replayed.purchases],
        )

        generated_output = StringIO()
        replayed_output = StringIO()
        with redirect_stdout(generated_output):
            print_result(generated, settings["target"])
        with redirect_stdout(replayed_output):
            print_result(replayed, settings["target"])
        self.assertEqual(generated_output.getvalue(), replayed_output.getvalue())


if __name__ == "__main__":
    unittest.main()

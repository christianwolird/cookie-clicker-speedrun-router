import tempfile
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from make_route import load_category, print_result, save_route
from scripts.extract_public_routes import extract_routes
from scripts.replay_route import execute_route, load_route, main
from src.algorithms import DEFAULT_ALGORITHM, RouteResult, get_algorithm
from src.gamestate import Gamestate


REPOSITORY = Path(__file__).resolve().parent.parent


class RouteFileTests(unittest.TestCase):
    def test_stored_routes_use_the_exact_metadata_schema(self):
        expected = {
            "name",
            "source",
            "version",
            "target",
            "click_rate",
            "initial_state",
        }
        for path in (REPOSITORY / "routes").glob("**/*.route"):
            with self.subTest(path=path):
                plan = load_route(path)
                self.assertTrue(plan.actions)
                keys = {
                    line.partition("=")[0].strip()
                    for line in path.read_text().splitlines()
                    if "=" in line
                }
                self.assertEqual(keys, expected)

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
                    self.assertEqual(
                        result.final_gamestate.lifetime_cookies,
                        plan.target,
                    )
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
            self.assertNotIn("errand_duration = ", contents)
            self.assertNotIn("purchase_click_rate = ", contents)
            self.assertNotIn("allow_upgrades = ", contents)
            self.assertRegex(contents, r"(?m)^buy \S+")
            self.assertIn("upgrade Reinforced index finger", contents)
            self.assertNotRegex(
                contents,
                r"(?m)^upgrade (Cursor|Grandma|Farm|Mine|Factory) \d+$",
            )
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
        result = RouteResult(Gamestate("1.0466"), ())

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

        execute.assert_called_once_with(
            plan,
            "1.0466",
            on_purchase=None,
            errand_duration=1.0,
            purchase_click_rate=5.0,
        )

    def test_saved_generated_route_is_replay_source_of_truth(self):
        settings = load_category("one_million")
        settings["algorithm"] = DEFAULT_ALGORITHM
        settings["target"] = 1_000
        initial_gamestate = Gamestate(settings["version"])
        initial_gamestate.click_rate = settings["click_rate"]
        initial_gamestate.upgrades_allowed = settings["allow_upgrades"]
        generated = get_algorithm(settings["algorithm"]).find_route(
            initial_gamestate,
            settings["target"],
            price_cutoff_multiplier=settings["price_cutoff_multiplier"],
        )

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
        metadata_keys = {
            line.partition("=")[0].strip()
            for line in contents.splitlines()
            if "=" in line
        }
        self.assertEqual(
            metadata_keys,
            {
                "name",
                "source",
                "version",
                "target",
                "click_rate",
                "initial_state",
            },
        )
        self.assertIn("upgrade Reinforced index finger", contents)
        self.assertNotIn("upgrade Cursor 1", contents)
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

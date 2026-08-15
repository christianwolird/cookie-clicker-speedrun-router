import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from make_route import RouteResult, available_categories, load_category, main


REPOSITORY = Path(__file__).resolve().parent.parent
CATEGORIES = REPOSITORY / "categories"


class CategoryConfigTests(unittest.TestCase):
    def test_expected_categories_are_plaintext_config_files(self):
        self.assertEqual(
            set(available_categories()),
            {"one_million", "neverclick", "hardcore", "heavenly_chip"},
        )
        self.assertFalse(any(CATEGORIES.glob("*.py")))

        for name in available_categories():
            with self.subTest(name=name):
                settings = load_category(name)
                self.assertIn("version", settings)
                self.assertIn("target", settings)
                self.assertIn("click_rate", settings)
                self.assertIn("initial_state", settings)
                self.assertIn("allow_upgrades", settings)

    def test_category_discovery_and_loading_are_not_name_hard_coded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "custom.conf"
            path.write_text("target = 123\nclick_rate = 7.5\n")

            self.assertEqual(available_categories(directory), ("custom",))
            self.assertEqual(
                load_category("custom", directory),
                {"target": 123, "click_rate": 7.5},
            )

    def test_cli_settings_override_category_defaults(self):
        captured = {}

        def fake_find_route(game, target, on_purchase):
            captured["game"] = game
            captured["target"] = target
            game.cookies = target
            return RouteResult(game, ())

        with (
            patch("make_route.find_route", side_effect=fake_find_route),
            redirect_stdout(StringIO()),
        ):
            main(
                [
                    "--category",
                    "one_million",
                    "--version",
                    "1.0466",
                    "--click-rate",
                    "20",
                    "--purchase-delay",
                    "0.25",
                ]
            )

        game = captured["game"]
        self.assertEqual(captured["target"], 1_000_000)
        self.assertEqual(game.version, "1.0466")
        self.assertEqual(game.clickrate, 20)
        self.assertEqual(game.purchase_delay, 0.25)

    def test_cli_can_override_category_initial_state(self):
        captured = {}

        def fake_find_route(game, target, on_purchase):
            captured["game"] = game
            game.cookies = target
            return RouteResult(game, ())

        with (
            patch("make_route.find_route", side_effect=fake_find_route),
            redirect_stdout(StringIO()),
        ):
            main(
                [
                    "--category",
                    "neverclick",
                    "--fresh-start",
                    "--click-rate",
                    "20",
                ]
            )

        game = captured["game"]
        self.assertEqual(game.num_buildings["Cursor"], 0)
        self.assertEqual(game.clickrate, 20)

    def test_cli_can_enable_upgrades_disabled_by_category(self):
        captured = {}

        def fake_find_route(game, target, on_purchase):
            captured["game"] = game
            game.cookies = target
            return RouteResult(game, ())

        with (
            patch("make_route.find_route", side_effect=fake_find_route),
            redirect_stdout(StringIO()),
        ):
            main(["--category", "hardcore", "--allow-upgrades"])

        game = captured["game"]
        self.assertTrue(game.allow_upgrades)


if __name__ == "__main__":
    unittest.main()

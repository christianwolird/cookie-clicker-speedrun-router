import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from make_route import available_categories, load_category, main
from src.algorithms import RouteResult


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
            path.write_text(
                "algorithm = cookie_scoring\n"
                "target = 123\n"
                "click_rate = 7.5\n"
            )

            self.assertEqual(available_categories(directory), ("custom",))
            self.assertEqual(
                load_category("custom", directory),
                {
                    "algorithm": "cookie_scoring",
                    "target": 123,
                    "click_rate": 7.5,
                },
            )

    def test_cli_settings_override_category_defaults(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_horizon_multiplier,
            on_purchase,
        ):
            captured["initial_gamestate"] = initial_gamestate
            captured["target"] = target
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
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
                    "--errand-duration",
                    "0.25",
                    "--purchase-click-rate",
                    "4",
                ]
            )

        gamestate = captured["initial_gamestate"]
        self.assertEqual(captured["target"], 1_000_000)
        self.assertEqual(gamestate.version, "1.0466")
        self.assertEqual(gamestate.click_rate, 20)
        self.assertEqual(gamestate.errand_duration, 0.25)
        self.assertEqual(gamestate.purchase_click_rate, 4)

    def test_cli_can_override_category_initial_state(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_horizon_multiplier,
            on_purchase,
        ):
            captured["initial_gamestate"] = initial_gamestate
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
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

        gamestate = captured["initial_gamestate"]
        self.assertEqual(gamestate.building_counts["Cursor"], 0)
        self.assertEqual(gamestate.click_rate, 20)

    def test_cli_can_enable_upgrades_disabled_by_category(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_horizon_multiplier,
            on_purchase,
        ):
            captured["initial_gamestate"] = initial_gamestate
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
            redirect_stdout(StringIO()),
        ):
            main(["--category", "hardcore", "--allow-upgrades"])

        gamestate = captured["initial_gamestate"]
        self.assertTrue(gamestate.upgrades_allowed)


if __name__ == "__main__":
    unittest.main()

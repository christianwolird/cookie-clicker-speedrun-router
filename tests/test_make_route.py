import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from make_route import (
    LivePurchaseTable,
    available_algorithms,
    format_purchase_table,
    format_time,
    local_route_path,
    main,
    save_route,
)
from src.algorithms import RouteResult
from src.gamestate import Gamestate, Purchase


class RouteTests(unittest.TestCase):
    def test_time_format_rounds_across_minute_boundary(self):
        self.assertEqual(format_time(59.96), "1:00.0")
        self.assertEqual(format_time(125.24), "2:05.2")

    def test_purchase_table_has_repeated_headers_and_one_decimal_place(self):
        purchases = [
            Purchase(
                "buy",
                f"Item {number}",
                number + 0.24,
                number * 1_234.56,
            )
            for number in range(1, 12)
        ]

        table = format_purchase_table(purchases)

        self.assertEqual(table.count("Cookies produced"), 2)
        self.assertIn("\n\n  #", table)
        self.assertIn("0:01.2", table)
        self.assertIn("1,234.6", table)

    def test_live_purchase_table_repeats_headers_in_blocks(self):
        output = StringIO()
        table = LivePurchaseTable(item_width=12)

        with redirect_stdout(output):
            for number in range(1, 12):
                table.print_purchase(
                    Purchase("buy", f"Item {number}", number, number)
                )

        self.assertEqual(output.getvalue().count("Cookies produced"), 2)
        self.assertIn("\n\n  #", output.getvalue())

    def test_cli_prints_final_time_after_live_table(self):
        final_gamestate = Gamestate()
        final_gamestate.age = 123.456
        final_gamestate.lifetime_cookies = 1_000_000
        output = StringIO()

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_cutoff_multiplier,
            on_purchase,
        ):
            purchase = Purchase("buy", "Streamed item", 1.2, 15)
            on_purchase(purchase)
            return RouteResult(final_gamestate, (purchase,))

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
            redirect_stdout(output),
        ):
            main(["--verbose"])

        self.assertLess(
            output.getvalue().index("Streamed item"),
            output.getvalue().index("Target:"),
        )
        self.assertEqual(output.getvalue().count("Streamed item"), 1)
        self.assertTrue(output.getvalue().rstrip().endswith("Final time: 2:03.5"))

    def test_cli_sets_price_cutoff_multiplier(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_cutoff_multiplier,
            on_purchase,
        ):
            captured["multiplier"] = price_cutoff_multiplier
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
            redirect_stdout(StringIO()),
        ):
            main(["--price-cutoff-multiplier", "4.0"])

        self.assertEqual(captured["multiplier"], 4.0)

    def test_cli_selects_game_version(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_cutoff_multiplier,
            on_purchase,
        ):
            captured["version"] = initial_gamestate.version
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
            redirect_stdout(StringIO()),
        ):
            main(["--version", "1.0466"])

        self.assertEqual(captured["version"], "1.0466")

    def test_cli_configures_neverclick_and_no_upgrades(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_cutoff_multiplier,
            on_purchase,
        ):
            captured["initial_gamestate"] = initial_gamestate
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
            redirect_stdout(StringIO()),
        ):
            main(["--neverclick-start", "--no-upgrades"])

        gamestate = captured["initial_gamestate"]
        self.assertEqual(gamestate.click_rate, 0)
        self.assertEqual(gamestate.lifetime_cookies, 1_000_000)
        self.assertEqual(gamestate.handmade_cookies, 15)
        self.assertEqual(gamestate.building_counts["Cursor"], 1)
        self.assertFalse(gamestate.upgrades_allowed)

    def test_cli_saves_only_when_requested(self):
        final_gamestate = Gamestate()
        final_gamestate.lifetime_cookies = 1_000_000
        result = RouteResult(final_gamestate, ())

        with (
            patch("make_route.calculate_route", return_value=result),
            patch(
                "make_route.save_route",
                return_value=(
                    Path(__file__).resolve().parents[1]
                    / "routes"
                    / "local"
                    / "test.route"
                ),
            ) as save,
            redirect_stdout(StringIO()),
        ):
            main(["--save", "routes/local/test.route"])

        save.assert_called_once()
        self.assertEqual(
            save.call_args.args[0],
            Path(__file__).resolve().parents[1]
            / "routes"
            / "local"
            / "test.route",
        )

    def test_save_destination_is_an_explicit_local_route_file(self):
        expected = (
            Path(__file__).resolve().parents[1]
            / "routes"
            / "local"
            / "one_million_10_cps.route"
        )

        self.assertEqual(
            local_route_path("routes/local/one_million_10_cps.route"),
            expected,
        )
        with self.assertRaisesRegex(ValueError, "end in .route"):
            local_route_path("routes/local/no_extension")
        with self.assertRaisesRegex(ValueError, "inside routes/local"):
            local_route_path("routes/from_online/not_local.route")

    def test_save_route_refuses_to_replace_a_file_without_overwrite(self):
        result = RouteResult(Gamestate(), ())
        settings = {
            "version": "2.031",
            "target": 1,
            "click_rate": 10.0,
            "initial_state": "fresh",
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.route"
            path.write_text("existing")
            with self.assertRaises(FileExistsError):
                save_route(path, settings, result)

    def test_cli_selects_algorithm(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_cutoff_multiplier,
            on_purchase,
        ):
            captured["algorithm"] = algorithm_name
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
            redirect_stdout(StringIO()),
        ):
            main(["--algorithm", "naive_scoring"])

        self.assertEqual(
            available_algorithms(),
            ("age_scoring", "naive_scoring"),
        )
        self.assertEqual(captured["algorithm"], "naive_scoring")

    def test_cli_configures_both_parts_of_errand_timing(self):
        captured = {}

        def fake_calculate_route(
            algorithm_name,
            initial_gamestate,
            target,
            price_cutoff_multiplier,
            on_purchase,
        ):
            captured["errand_duration"] = initial_gamestate.errand_duration
            captured["purchase_click_rate"] = (
                initial_gamestate.purchase_click_rate
            )
            initial_gamestate.lifetime_cookies = target
            return RouteResult(initial_gamestate, ())

        with (
            patch("make_route.calculate_route", side_effect=fake_calculate_route),
            redirect_stdout(StringIO()),
        ):
            main(
                [
                    "--errand-duration",
                    "0.75",
                    "--purchase-click-rate",
                    "4",
                ]
            )

        self.assertEqual(captured["errand_duration"], 0.75)
        self.assertEqual(captured["purchase_click_rate"], 4)


if __name__ == "__main__":
    unittest.main()

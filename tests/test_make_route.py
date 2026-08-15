import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from make_route import (
    LivePurchaseTable,
    RouteResult,
    find_route,
    format_purchase_table,
    format_time,
    local_route_path,
    main,
    save_route,
)
from src.game import Game, Purchase, purchase_score


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
        game = Game()
        game.age = 123.456
        game.cookies = 1_000_000
        output = StringIO()

        def fake_find_route(start, target, on_purchase):
            purchase = Purchase("buy", "Streamed item", 1.2, 15)
            on_purchase(purchase)
            return RouteResult(game, (purchase,))

        with (
            patch("make_route.find_route", side_effect=fake_find_route),
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

        def fake_find_route(game, target, on_purchase):
            captured["multiplier"] = game.price_cutoff_multiplier
            game.cookies = target
            return RouteResult(game, ())

        with (
            patch("make_route.find_route", side_effect=fake_find_route),
            redirect_stdout(StringIO()),
        ):
            main(["--price-cutoff-multiplier", "4.0"])

        self.assertEqual(captured["multiplier"], 4.0)

    def test_cli_selects_game_version(self):
        captured = {}

        def fake_find_route(game, target, on_purchase):
            captured["version"] = game.version
            game.cookies = target
            return RouteResult(game, ())

        with (
            patch("make_route.find_route", side_effect=fake_find_route),
            redirect_stdout(StringIO()),
        ):
            main(["--version", "1.0466"])

        self.assertEqual(captured["version"], "1.0466")

    def test_cli_configures_neverclick_and_no_upgrades(self):
        captured = {}

        def fake_find_route(game, target, on_purchase):
            captured["game"] = game
            game.cookies = target
            return RouteResult(game, ())

        with (
            patch("make_route.find_route", side_effect=fake_find_route),
            redirect_stdout(StringIO()),
        ):
            main(["--neverclick-start", "--no-upgrades"])

        game = captured["game"]
        self.assertEqual(game.clickrate, 0)
        self.assertEqual(game.cookies, 1_000_000)
        self.assertEqual(game.handmade_cookies, 15)
        self.assertEqual(game.num_buildings["Cursor"], 1)
        self.assertFalse(game.allow_upgrades)

    def test_cli_saves_only_when_requested(self):
        game = Game()
        game.cookies = 1_000_000
        result = RouteResult(game, ())

        with (
            patch("make_route.find_route", return_value=result),
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
            Path(__file__).resolve().parents[1] / "routes" / "local" / "test.route",
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
        game = Game()
        result = RouteResult(game, ())
        settings = {
            "version": "2.031",
            "target": 1,
            "click_rate": 10.0,
            "purchase_delay": 0.5,
            "price_cutoff_multiplier": 2.0,
            "initial_state": "fresh",
            "allow_upgrades": True,
        }

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "existing.route"
            path.write_text("existing")
            with self.assertRaises(FileExistsError):
                save_route(path, settings, result)

    def test_purchase_score_matches_pairwise_ordering_formula(self):
        class State:
            def __init__(self, cookies, cps):
                self.cookies = cookies
                self._cps = cps

            def cps(self):
                return self._cps

        parent = State(0, 10)
        better_first = State(100, 20)
        worse_first = State(80, 15)

        self.assertLess(
            purchase_score(parent, better_first),
            purchase_score(parent, worse_first),
        )

    def test_search_beats_buying_nothing(self):
        game = Game()
        game.clickrate = 8
        no_purchases = game.finish(100_000)

        route = find_route(game, target=100_000)

        self.assertLess(route.game.age, no_purchases.age)
        self.assertEqual(route.game.cookies, 100_000)
        self.assertTrue(route.purchases)

    def test_search_reports_each_purchase_as_it_is_selected(self):
        game = Game()
        purchases = []

        route = find_route(game, target=1_000, on_purchase=purchases.append)

        self.assertEqual(purchases, list(route.purchases))


if __name__ == "__main__":
    unittest.main()

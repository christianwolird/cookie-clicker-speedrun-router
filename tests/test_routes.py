import tempfile
import unittest
from pathlib import Path

from scripts.errandify import (
    errandify_plan,
    save_errandified_route,
)
from scripts.extract_public_routes import extract_routes
from src.config import available_categories, load_category, local_route_path
from src.presentation import format_route, format_time
from src.routes import (
    RouteAction,
    RoutePlan,
    execute_route,
    load_route,
    write_route,
)


REPOSITORY = Path(__file__).resolve().parents[1]
ONLINE_SINGLETONS = REPOSITORY / "routes" / "from_online" / "singletons"


class RouteTests(unittest.TestCase):
    def test_all_stored_routes_parse_and_reach_their_targets(self):
        paths = sorted((REPOSITORY / "routes").glob("**/*.route"))
        self.assertTrue(paths)

        for path in paths:
            with self.subTest(path=path):
                plan = load_route(path)
                result = execute_route(plan)
                self.assertEqual(result.final_gamestate.lifetime_cookies, plan.target)

    def test_route_round_trip_preserves_metadata_and_errands(self):
        source = load_route(
            ONLINE_SINGLETONS / "one_million_fast_clicks_15_cps_dha.route"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_route(
                Path(directory) / "copy.route",
                source,
                comment="test",
                explicit_errands=False,
            )
            loaded = load_route(path)

        self.assertEqual(loaded, source)

    def test_replay_uses_recorded_errand_grouping(self):
        plan = RoutePlan(
            name="grouped",
            source="test",
            version="2.031",
            target=1_000,
            click_rate=10,
            initial_state="fresh",
            algorithm="test",
            errand_duration=1,
            purchase_click_rate=5,
            upgrades_enabled=True,
            errands_enabled=True,
            errands=(
                (
                    RouteAction("buy", "Cursor"),
                    RouteAction("upgrade", "Reinforced index finger"),
                ),
            ),
        )

        result = execute_route(plan)

        self.assertEqual(len(result.errands[0]), 2)
        self.assertAlmostEqual(result.final_gamestate.cookies_per_click(), 2)

    def test_online_extractor_produces_canonical_singletons(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = extract_routes(
                REPOSITORY / "routes" / "dha_spreadsheets",
                directory,
            )

            self.assertEqual(len(paths), 9)
            for path in paths:
                plan = load_route(path)
                self.assertFalse(plan.errands_enabled)
                self.assertTrue(all(len(errand) == 1 for errand in plan.errands))
                self.assertEqual(plan.errand_duration, 1.0)
                self.assertEqual(plan.purchase_click_rate, 5.0)

    def test_errandifier_preserves_order_and_keeps_sales_singleton(self):
        source = load_route(
            ONLINE_SINGLETONS / "hardcore_left_clicks_10_cps_lookas123.route"
        )
        errands = errandify_plan(source)

        self.assertEqual(
            tuple(action for errand in errands for action in errand),
            source.actions,
        )
        self.assertTrue(any(len(errand) > 1 for errand in errands))
        self.assertTrue(
            all(
                len(errand) == 1
                for errand in errands
                if any(action.operation == "sell" for action in errand)
            )
        )

        with tempfile.TemporaryDirectory() as directory:
            path = save_errandified_route(
                Path(directory) / "errandified.route",
                source,
                errands,
            )
            saved = load_route(path)
        self.assertEqual(saved.algorithm, "contiguous_errand_dp")
        self.assertEqual(saved.max_errand_size, 100)

    def test_categories_are_data_driven(self):
        self.assertEqual(
            set(available_categories()),
            {
                "10k",
                "100k",
                "one_million",
                "neverclick",
                "hardcore",
                "heavenly_chip",
            },
        )
        self.assertEqual(load_category("neverclick")["algorithm"], "singleton_errands")
        self.assertEqual(load_category("10k")["algorithm"], "fuzzy_astar")
        self.assertEqual(load_category("10k")["astar_fuzzy_scale"], 1.0)
        self.assertEqual(load_category("100k")["target"], 100_000)
        self.assertFalse(load_category("hardcore")["upgrades_enabled"])

    def test_output_format_has_one_done_row(self):
        plan = load_route(
            ONLINE_SINGLETONS / "neverclick_neverclick_36champ.route"
        )
        result = execute_route(plan)
        output = format_route(result, plan.target, include_purchases=False)

        self.assertEqual(format_time(59.96), "1:00.0")
        self.assertEqual(output.count("Cookies produced"), 1)
        self.assertIn("Done!", output.splitlines()[-1])

    def test_local_route_destination_is_restricted(self):
        with self.assertRaisesRegex(ValueError, "routes/local"):
            local_route_path("routes/from_online/not-local.route")


if __name__ == "__main__":
    unittest.main()

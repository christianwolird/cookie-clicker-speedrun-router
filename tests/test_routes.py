import tempfile
import unittest
from pathlib import Path
from dataclasses import replace

from community_spreadsheets.extract_routes_from_spreadsheet import extract_routes
from tools.errandifier import (
    _default_output,
    errandify_plan,
    save_errandified_route,
)
from ccsr.config import (
    available_goals,
    available_route_profiles,
    available_player_profiles,
    create_initial_gamestate,
    load_goal,
    load_route_profile,
    load_player_profile,
)
from ccsr.routes import (
    RouteAction,
    RoutePlan,
    execute_route,
    load_route,
    write_route,
)


REPOSITORY = Path(__file__).resolve().parents[1]
ROUTES = REPOSITORY / "routes"


class RouteTests(unittest.TestCase):
    def test_errandifier_defaults_to_prefixed_file_in_same_directory(self):
        source = ROUTES / "hardcore-10cps/community_quickster_dha.route"

        directory = ROUTES / "hardcore-10cps"
        self.assertEqual(_default_output(source.parent), directory)
        self.assertEqual(_default_output(source), directory / "community_errandified_dha.route")

    def test_all_stored_routes_parse_and_reach_targets(self):
        paths = sorted((REPOSITORY / "routes").glob("**/*.route"))
        self.assertEqual(len(tuple(ROUTES.glob("*/community_quickster_*.route"))), 9)
        self.assertGreaterEqual(len(paths), 9)

        for path in paths:
            with self.subTest(path=path):
                plan = load_route(path)
                result = execute_route(plan)
                self.assertEqual(result.final_gamestate.lifetime_cookies, plan.target)
                self.assertEqual(plan.route_profile, path.parent.name)
                self.assertIn(plan.route_profile, available_route_profiles())
                if path.name.startswith("community_quickster_"):
                    self.assertTrue(plan.for_quickster)
                elif path.name.startswith("community_errandified_"):
                    self.assertFalse(plan.for_quickster)
                    self.assertEqual(plan.max_errand_size, 100)

        self.assertEqual(len(tuple(ROUTES.glob("*/community_errandified_*.route"))), 8)
        neverclick = ROUTES / "neverclick-0cps/community_errandified_36champ.route"
        self.assertFalse(neverclick.exists())

    def test_route_round_trip_preserves_metadata(self):
        source = load_route(
            ROUTES / "million-15cps/community_quickster_dha.route"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = write_route(
                Path(directory) / "copy.route",
                source,
                explicit_errands=False,
            )
            loaded = load_route(path)

        self.assertEqual(loaded, source)

    def test_online_routes_record_player_profiles_and_omit_delays(self):
        expected = {
            "neverclick-0cps": "neverclick",
            "million-10cps": "default_10_cps",
            "million-15cps": "default_15_cps",
            "million-200cps": "default_200_cps",
        }
        for path in ROUTES.glob("*/community_quickster_*.route"):
            plan = load_route(path)
            contents = path.read_text()
            self.assertTrue(plan.for_quickster)
            self.assertNotIn("errand_delay", contents)
            self.assertNotIn("item_delay", contents)
            if path.parent.name in expected:
                self.assertEqual(plan.player_profile, expected[path.parent.name])

    def test_online_extractor_reproduces_canonical_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            paths = extract_routes(
                REPOSITORY / "community_spreadsheets",
                output,
            )

            self.assertEqual(len(paths), 9)
            for path in paths:
                self.assertEqual(
                    load_route(path),
                    load_route(ROUTES / path.relative_to(output)),
                )

    def test_errandifier_uses_selected_player_profile(self):
        source = load_route(
            ROUTES / "hardcore-10cps/community_quickster_lookas123.route"
        )
        casual = load_player_profile("casual")
        errands = errandify_plan(source, casual)

        self.assertTrue(any(len(errand) > 1 for errand in errands))
        with tempfile.TemporaryDirectory() as directory:
            path = save_errandified_route(
                Path(directory) / "errandified.route",
                source,
                casual,
                errands,
            )
            saved = load_route(path)

        self.assertFalse(saved.for_quickster)
        self.assertEqual(saved.algorithm, "errandifier")
        self.assertEqual(saved.player_profile, "casual")
        self.assertEqual(saved.errand_delay, 1.0)
        self.assertEqual(saved.item_delay, 0.3)

    def test_human_route_replay_can_override_player(self):
        plan = RoutePlan(
            name="grouped",
            source="test",
            goal="10k",
            player_profile="default_10_cps",
            version="2.031",
            target=1_000,
            click_rate=10,
            initial_state="fresh",
            algorithm="test",
            upgrades_enabled=True,
            for_quickster=False,
            errands=(
                (
                    RouteAction("buy", "Cursor"),
                    RouteAction("upgrade", "Reinforced index finger"),
                ),
            ),
            errand_delay=0.8,
            action_delay=0.2,
        )
        casual = load_player_profile("casual")

        default_result = execute_route(plan)
        casual_result = execute_route(plan, player=casual)

        self.assertNotEqual(
            default_result.final_gamestate.age,
            casual_result.final_gamestate.age,
        )

    def test_route_profile_and_player_configuration_are_separate(self):
        profile = load_route_profile("million-25cps")
        casual = load_player_profile("casual")
        gamestate = create_initial_gamestate(profile, casual)

        self.assertEqual(
            set(available_route_profiles()),
            {
                "10k-10cps", "100k-10cps", "million-25cps", "million-250cps",
                "neverclick-0cps", "hardcore-250cps", "hardcore-10cps", "heavenly-chip-15cps",
                "million-10cps", "million-15cps", "million-200cps",
            },
        )
        self.assertEqual(gamestate.click_rate, 7)
        self.assertEqual(gamestate.errand_delay, 1.0)
        self.assertEqual(gamestate.item_delay, 0.3)

    def test_goal_is_independent_of_version(self):
        profile = load_route_profile("million-250cps")
        self.assertEqual(profile.goal, "one_million")
        self.assertEqual(profile.version, "2.031")
        self.assertNotIn("neverclick", available_goals())
        self.assertFalse(hasattr(load_goal("one_million"), "version"))
        for version, farm_price in (
            ("1.0466", 500),
            ("2.031", 1_100),
        ):
            with self.subTest(version=version):
                configured = replace(profile, version=version)
                self.assertEqual(configured.target, 1_000_000)
                gamestate = create_initial_gamestate(configured)
                self.assertEqual(gamestate.building_price("Farm"), farm_price)

    def test_method_and_default_player_profiles(self):
        profiles = set(available_player_profiles())
        self.assertEqual(profiles, {
            "casual", "neverclick", "default_10_cps", "default_15_cps",
            "default_200_cps", "default_25_cps", "default_250_cps", "trained_250_cps",
        })

        method_rates = {
            "default_25_cps": 25,
            "default_250_cps": 250,
        }
        for name, click_rate in method_rates.items():
            with self.subTest(name=name):
                profile = load_player_profile(name)
                self.assertEqual(profile.click_rate, click_rate)
                self.assertEqual(profile.errand_delay, 0.8)
                self.assertEqual(profile.item_delay, 0.2)

        for name in (
            "default_10_cps",
            "default_15_cps",
            "default_200_cps",
        ):
            with self.subTest(name=name):
                self.assertEqual(load_player_profile(name).item_delay, 0.2)

        default = load_player_profile("default_10_cps")
        self.assertEqual(default.click_rate, 10)
        self.assertEqual(default.errand_delay, 0.8)
        self.assertEqual(default.item_delay, 0.2)

        neverclick = load_player_profile("neverclick")
        self.assertEqual(neverclick.errand_delay, 0.0)
        self.assertEqual(neverclick.item_delay, 0.0)

    def test_neverclick_player_supplies_starting_state(self):
        profile = load_route_profile("neverclick-0cps")
        self.assertEqual(profile.goal, "one_million")
        gamestate = create_initial_gamestate(profile)
        self.assertEqual(gamestate.click_rate, 0)
        self.assertEqual(gamestate.lifetime_cookies, 15)
        self.assertEqual(gamestate.building_counts["Cursor"], 1)
        self.assertEqual(gamestate.bulk_size, 1)
        self.assertTrue(gamestate.selling_allowed)
        fast = create_initial_gamestate(profile, load_player_profile("default_250_cps"))
        self.assertEqual(fast.click_rate, 250)
        self.assertEqual(fast.building_counts["Cursor"], 0)


if __name__ == "__main__":
    unittest.main()

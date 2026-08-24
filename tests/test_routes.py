import tempfile
import unittest
from pathlib import Path

from scripts.extract_online_routes import extract_routes
from tools.errandifier import (
    _default_output,
    errandify_plan,
    save_errandified_route,
)
from ccsr.config import (
    available_categories,
    available_player_profiles,
    create_initial_gamestate,
    load_category,
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
ONLINE_QUICKSTER = REPOSITORY / "routes/online/quickster_originals"
ONLINE_ERRANDED = REPOSITORY / "routes/online/erranded"


class RouteTests(unittest.TestCase):
    def test_errandifier_defaults_to_erranded_directory(self):
        source = ONLINE_QUICKSTER / "hardcore_left_clicks_10_cps_dha.route"

        self.assertEqual(_default_output(ONLINE_QUICKSTER), ONLINE_ERRANDED)
        self.assertEqual(_default_output(source), ONLINE_ERRANDED / source.name)

    def test_all_stored_routes_parse_and_reach_targets(self):
        paths = sorted((REPOSITORY / "routes").glob("**/*.route"))
        self.assertEqual(len(tuple(ONLINE_QUICKSTER.glob("*.route"))), 9)
        self.assertGreaterEqual(len(paths), 9)

        for path in paths:
            with self.subTest(path=path):
                plan = load_route(path)
                result = execute_route(plan)
                self.assertEqual(result.final_gamestate.lifetime_cookies, plan.target)
                if path.parent == ONLINE_QUICKSTER:
                    self.assertTrue(plan.for_quickster)
                elif path.parent == ONLINE_ERRANDED:
                    self.assertFalse(plan.for_quickster)
                    self.assertEqual(plan.max_errand_size, 100)

        self.assertEqual(len(tuple(ONLINE_ERRANDED.glob("*.route"))), 8)
        neverclick = ONLINE_ERRANDED / "neverclick_neverclick_36champ.route"
        self.assertFalse(neverclick.exists())

    def test_route_round_trip_preserves_metadata(self):
        source = load_route(
            ONLINE_QUICKSTER / "one_million_fast_clicks_15_cps_dha.route"
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
            "neverclick_neverclick_36champ.route": "default_neverclick",
            "one_million_left_clicks_10_cps_iwer_sonsch.route": (
                "default_10_cps"
            ),
            "one_million_fast_clicks_15_cps_dha.route": "default_15_cps",
            "one_million_ultra_clicks_200_cps_lily2.route": (
                "default_200_cps"
            ),
        }
        for path in ONLINE_QUICKSTER.glob("*.route"):
            plan = load_route(path)
            contents = path.read_text()
            self.assertTrue(plan.for_quickster)
            self.assertNotIn("errand_delay", contents)
            self.assertNotIn("item_delay", contents)
            if path.name in expected:
                self.assertEqual(plan.player_profile, expected[path.name])

    def test_online_extractor_reproduces_canonical_routes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            paths = extract_routes(
                REPOSITORY / "routes/online/spreadsheets",
                output,
            )

            self.assertEqual(len(paths), 9)
            for path in paths:
                self.assertEqual(
                    path.read_text(),
                    (ONLINE_QUICKSTER / path.name).read_text(),
                )

    def test_errandifier_uses_selected_player_profile(self):
        source = load_route(
            ONLINE_QUICKSTER / "hardcore_left_clicks_10_cps_lookas123.route"
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
            category="10k",
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
            item_delay=0.2,
        )
        casual = load_player_profile("casual")

        default_result = execute_route(plan)
        casual_result = execute_route(plan, player=casual)

        self.assertNotEqual(
            default_result.final_gamestate.age,
            casual_result.final_gamestate.age,
        )

    def test_category_and_player_configuration_are_separate(self):
        category = load_category("one_million")
        casual = load_player_profile("casual")
        gamestate = create_initial_gamestate(category, casual)

        self.assertEqual(
            set(available_categories()),
            {"10k", "100k", "one_million", "neverclick", "hardcore", "heavenly_chip"},
        )
        self.assertEqual(gamestate.click_rate, 7)
        self.assertEqual(gamestate.errand_delay, 1.0)
        self.assertEqual(gamestate.item_delay, 0.3)

    def test_method_and_default_player_profiles(self):
        profiles = set(available_player_profiles())
        self.assertNotIn("amateur", profiles)
        self.assertNotIn("veteran", profiles)
        self.assertNotIn("fast_click", profiles)
        self.assertFalse(any(name.startswith("community_") for name in profiles))

        method_rates = {
            "scroll_click": 50,
            "strum_click": 25,
            "mouse_move_click": 100,
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

        neverclick = load_player_profile("default_neverclick")
        self.assertEqual(neverclick.errand_delay, 0.0)
        self.assertEqual(neverclick.item_delay, 0.0)

    def test_neverclick_category_disables_profile_clicking(self):
        category = load_category("neverclick")
        fast = load_player_profile("mouse_move_click")

        gamestate = create_initial_gamestate(category, fast)

        self.assertEqual(gamestate.click_rate, 0)


if __name__ == "__main__":
    unittest.main()

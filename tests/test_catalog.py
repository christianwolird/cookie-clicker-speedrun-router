import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from dataclasses import replace
from pathlib import Path

from ccsr.config import (
    available_errand_profiles, load_player_profile, load_route_profile,
    create_initial_gamestate, load_errand_profile,
)
from ccsr.routes import RoutePlan, RouteAction, execute_route, load_route, write_route
from ccsr.routes.catalog import (
    entry_details, inspect_route, matches_profile, profile_catalog, profile_details, scan_routes,
)
from tools import route_catalog, greedy_router, beam_search_router
from tools.errandifier import _route_pairs
from ccsr.routes.layout import generated_route_path
from unittest.mock import patch


REPOSITORY = Path(__file__).resolve().parents[1]


def configured_plan(profile_name="million-250cps"):
    profile = load_route_profile(profile_name)
    player = load_player_profile(profile.player_profile)
    errands = load_errand_profile(profile.errand_profile)
    return RoutePlan(
        name="catalog fixture", source="this codebase", goal=profile.goal,
        route_profile=profile.name, achievement_curve=profile.achievement_curve,
        version=profile.version, target=profile.target, player_profile=player.name,
        click_rate=player.click_rate, initial_state=player.initial_state,
        algorithm="greedy_router", upgrades_enabled=profile.upgrades_enabled,
        for_quickster=False, errands=((RouteAction("buy", "Cursor", errands.bulk_size),),),
        errand_delay=player.errand_delay, action_delay=player.action_delay,
        errand_profile=errands.name, bulk_size=errands.bulk_size,
        selling_allowed=errands.selling_allowed,
    )


class CatalogTests(unittest.TestCase):
    def test_named_profiles_resolve_all_independent_axes(self):
        profiles = {profile["name"]: profile for profile in profile_catalog()}
        expected = {
            "million-250cps": (250, 10, False, "fresh"),
            "million-25cps": (25, 1, False, "fresh"),
            "neverclick-0cps": (0, 1, True, "neverclick"),
        }
        for name, values in expected.items():
            profile = profiles[name]
            self.assertEqual(profile["goal"], "one_million")
            self.assertEqual(profile["version"], "2.031")
            self.assertEqual(tuple(profile[key] for key in (
                "click_rate", "bulk_size", "selling_allowed", "initial_state",
            )), values)
        self.assertFalse((REPOSITORY / "config/categories").exists())
        self.assertEqual(set(available_errand_profiles()), {
            "single_no_selling", "single_with_selling",
            "bulk10_no_selling", "bulk10_with_selling",
        })

    def test_route_profile_rejects_bad_references_and_duplicate_fields(self):
        original = (REPOSITORY / "config/route_profiles/million-250cps.conf").read_text()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.conf"
            for content in (
                original.replace("one_million", "neverclick"),
                original.replace("2.031", "invalid"),
                original.replace("trained_250_cps", "quick_buy_250_cps"),
                original.replace("bulk10_no_selling", "bulk10"),
                original + "goal = 10k\n",
            ):
                path.write_text(content)
                with self.assertRaises(ValueError):
                    load_route_profile("test", directory)

    def test_player_starting_state_requires_zero_click_rate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.conf"
            path.write_text("click_rate = 250\nerrand_delay = 0.8\naction_delay = 0.2\ninitial_state = neverclick\n")
            with self.assertRaisesRegex(ValueError, "click_rate = 0"):
                load_player_profile("invalid", directory)

    def test_new_route_metadata_is_self_contained(self):
        plan = replace(configured_plan(), route_profile="retired-setup", player_profile="retired-player")
        with tempfile.TemporaryDirectory() as directory:
            path = write_route(Path(directory) / "snapshot.route", plan)
            contents = path.read_text()
            self.assertIn("goal = one_million", contents)
            self.assertIn("version = 2.031", contents)
            self.assertNotIn("category =", contents)
            loaded = load_route(path)
            self.assertEqual(loaded, plan)
            self.assertIsNone(inspect_route(path).error)
            self.assertEqual(execute_route(loaded).final_gamestate.lifetime_cookies, 1_000_000)

    def test_legacy_category_maps_to_goal_without_category_configs(self):
        source = REPOSITORY / "routes/neverclick-0cps/community_quickster_36champ.route"
        legacy = source.read_text().replace("goal = one_million", "category = neverclick")
        legacy = legacy.replace("route_profile = neverclick-0cps\n", "")
        legacy = legacy.replace("player_profile = neverclick", "player_profile = default_neverclick")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "legacy.route"
            path.write_text(legacy)
            plan = load_route(path)
        self.assertEqual(plan.goal, "one_million")
        self.assertEqual(plan.player_profile, "neverclick")
        self.assertEqual(plan.initial_state, "neverclick")
        self.assertIsNone(plan.route_profile)
        self.assertIsNone(plan.errand_profile)
        self.assertEqual(plan.version, "2.031")
        self.assertIsNone(inspect_route(source).error)

    def test_profile_filter_uses_actual_settings_not_saved_label(self):
        details = profile_details(load_route_profile("million-250cps"))
        plan = configured_plan()
        self.assertTrue(matches_profile(plan, details))
        for changed in (
            replace(plan, version="1.0466"), replace(plan, click_rate=25),
            replace(plan, action_delay=0.01), replace(plan, for_quickster=True),
            replace(plan, errand_profile=None), replace(plan, initial_state="neverclick"),
        ):
            self.assertFalse(matches_profile(changed, details))
        self.assertTrue(matches_profile(replace(plan, route_profile=None), details))

    def test_scan_reports_invalid_routes_and_keeps_valid_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            write_route(root / "valid.route", configured_plan())
            (root / "broken.route").write_text("not a route")
            entries = scan_routes(root)
        self.assertEqual(len(entries), 2)
        self.assertEqual(sum(entry.error is not None for entry in entries), 1)
        valid = next(entry for entry in entries if not entry.error)
        details = entry_details(valid, profiles=profile_catalog())
        self.assertEqual(details["matching_profiles"], ["million-250cps"])
        self.assertEqual(details["version"], "2.031")
        self.assertEqual(details["execution"], "human")
        self.assertGreater(details["finish_seconds"], 0)

    def test_catalog_filters_goal_version_and_execution_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan = configured_plan()
            write_route(root / "human-v2.route", plan)
            write_route(root / "quick-v2.route", replace(plan, for_quickster=True))
            write_route(root / "human-v1.route", replace(plan, version="1.0466"))
            output = io.StringIO()
            with redirect_stdout(output):
                route_catalog.main([
                    "list", "--root", directory, "--goal", "one_million",
                    "--version", "2.031", "--mode", "human", "--json",
                ])
            result = json.loads(output.getvalue())
            self.assertEqual([row["path"] for row in result["routes"]], ["human-v2.route"])
            self.assertFalse(result["errors"])
            output = io.StringIO()
            with redirect_stdout(output):
                route_catalog.main(["show", "human-v2.route", "--root", directory, "--json"])
            self.assertEqual(json.loads(output.getvalue())["action_delay"], 0.1)

    def test_cli_reports_catalog_errors_with_nonzero_status(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "broken.route").write_text("invalid")
            output = io.StringIO()
            with redirect_stdout(output), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                route_catalog.main(["list", "--root", directory, "--json"])
            self.assertEqual(error.exception.code, 1)
            self.assertEqual(len(json.loads(output.getvalue())["errors"]), 1)

    def test_type_filter_includes_community_variants_and_generated_baseline(self):
        output = io.StringIO()
        with redirect_stdout(output):
            route_catalog.main(["list", "--route-type", "hardcore-10cps", "--json"])
        rows = json.loads(output.getvalue())["routes"]
        self.assertEqual(len(rows), 5)
        self.assertEqual({row["route_kind"] for row in rows}, {
            "community_quickster", "community_errandified", "generated_greedy",
        })
        self.assertTrue(all(row["version"] == "1.0466" for row in rows))
        self.assertTrue(all(row["click_rate"] == 10 for row in rows))

    def test_batch_errandification_preserves_type_and_author_paths(self):
        root = REPOSITORY / "routes"
        pairs = _route_pairs(root, root)
        self.assertEqual(len(pairs), 9)
        for source, destination in pairs:
            self.assertTrue(source.name.startswith("community_quickster_"))
            self.assertTrue(destination.name.startswith("community_errandified_"))
            self.assertEqual(source.parent, destination.parent)
            self.assertEqual(source.name.removeprefix("community_quickster_"),
                             destination.name.removeprefix("community_errandified_"))
        with tempfile.TemporaryDirectory() as directory:
            redirected = _route_pairs(root, Path(directory))
            self.assertEqual(len(redirected), 9)
            self.assertEqual(len({destination for _, destination in redirected}), 9)

    def test_generated_save_paths_use_type_and_kind_and_reject_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "million-250cps/generated_beam.route"
            self.assertEqual(generated_route_path("generated_beam.route", "million-250cps", "generated_beam", root), expected)
            self.assertEqual(generated_route_path(expected.name, "million-250cps", "generated_beam", root), expected)
            self.assertEqual(generated_route_path(expected, "million-250cps", "generated_beam", root), expected)
            for destination in ("../outside.route", str(root / "outside.route"),
                                "nested/test.route", "generated_greedy_test.route"):
                with self.assertRaises(ValueError):
                    generated_route_path(destination, "million-250cps", "generated_beam", root)

    def test_router_saves_resolved_profile_defaults_and_version_override(self):
        # Keep generated fixtures under the repository to exercise actual save
        # validation and relative-path reporting without touching stored routes.
        for tool, options in (
            (greedy_router, ["--queue-expansions", "3"]),
            (beam_search_router, ["--max-expansions", "3", "--errand-queue-expansions", "3"]),
        ):
            with tempfile.TemporaryDirectory(dir=REPOSITORY) as directory:
                path = Path(directory) / "10k-10cps/generated_greedy_test.route"
                if tool is beam_search_router:
                    path = Path(directory) / "10k-10cps/generated_beam_test.route"
                with patch.object(tool, "OUTPUT_DIRECTORY", Path(directory)), redirect_stdout(io.StringIO()):
                    tool.main(["--route-profile", "10k-10cps", "--version", "1.0466", "--save", "test.route", *options])
                plan = load_route(path)
                self.assertEqual(plan.goal, "10k")
                self.assertEqual(plan.route_profile, "10k-10cps")
                self.assertEqual(plan.version, "1.0466")
                self.assertEqual(plan.player_profile, "default_10_cps")
                self.assertEqual(plan.errand_profile, "single_no_selling")
                self.assertEqual(execute_route(plan).final_gamestate.lifetime_cookies, 10_000)


if __name__ == "__main__":
    unittest.main()

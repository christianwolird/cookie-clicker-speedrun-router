import io
import itertools
import tempfile
import unittest
import subprocess
import sys
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path

from ccsr.config import (
    ErrandProfile, create_initial_gamestate, load_category,
    load_errand_profile, load_player_profile,
)
from ccsr.errands.errandifier import partition_contiguous_actions
from ccsr.errands.generator import (
    Errand, _evaluate, added_purchase_errands, best_errand, generate_neighbors,
    initial_errands, errand_price,
)
from ccsr.game.gamestate import Gamestate
from ccsr.game.shop import execute_shop_errand
from ccsr.presentation import LiveRouteTable, format_route
from ccsr.routes import (
    RouteAction as Action, RoutePlan, RouteResult, action_errands,
    execute_route, load_route, write_route,
)
from ccsr.routing_algorithms.beam_search_router import find_route as beam_route, inventory_key
from ccsr.routing_algorithms.greedy_router import find_route as greedy_route


def state(profile="single", category="10k"):
    return create_initial_gamestate(
        load_category(category), load_player_profile("default_250_cps"),
        errand_profile=load_errand_profile(profile),
    )


def plan_for(initial, errands):
    return RoutePlan(
        name="test", source="test", category="10k", player_profile="default_250_cps",
        version=initial.version, target=10_000, click_rate=initial.click_rate,
        initial_state="fresh", algorithm="test", upgrades_enabled=True,
        for_quickster=False, errands=errands, errand_delay=initial.errand_delay,
        action_delay=initial.action_delay, errand_profile="recorded-settings",
        bulk_size=initial.bulk_size, selling_allowed=initial.selling_allowed,
    )


class ShopProfileTests(unittest.TestCase):
    def test_profiles_are_independent_of_player(self):
        for name, bulk, sales in (
            ("single", 1, False), ("single_with_sales", 1, True),
            ("bulk10", 10, False), ("bulk10_with_sales", 10, True),
        ):
            gamestate = state(name)
            self.assertEqual((gamestate.bulk_size, gamestate.selling_allowed), (bulk, sales))
            self.assertEqual(gamestate.action_delay, 0.2)
        with self.assertRaises(ValueError):
            ErrandProfile("invalid", 100)

    def test_player_delay_alias_and_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.conf"
            for setting in ("item_delay", "action_delay"):
                path.write_text(f"click_rate = 250\nerrand_delay = 0.8\n{setting} = 0.2\n")
                self.assertEqual(load_player_profile("test", directory).action_delay, 0.2)
            path.write_text(path.read_text() + "item_delay = 0.3\n")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_player_profile("test", directory)

    def test_single_generation_deduplicates_permutations(self):
        gamestate = state()
        empty = Errand((0,) * len(gamestate.building_catalog))
        frontier = {empty}
        for _ in range(3):
            frontier = {
                child for parent in frontier for child in added_purchase_errands(gamestate, parent)
                if not child.upgrades and not any(child.building_quantities[2:])
            }
        self.assertEqual(len(frontier), 4)  # CCC, CCG, CGG, GGG; not eight sequences.
        self.assertTrue(all(not errand.purchase_order for errand in frontier))

    def test_single_replay_permutations_are_equivalent(self):
        gamestate = state()
        actions = (Action("buy", "Cursor"), Action("buy", "Grandma"), Action("buy", "Cursor"))
        results = [execute_shop_errand(gamestate, order) for order in set(itertools.permutations(actions))]
        self.assertTrue(all(result[0].age == results[0][0].age for result in results))
        self.assertTrue(all(result[1] == results[0][1] for result in results))

    def test_bulk_partial_batches_obey_order(self):
        gamestate = state("bulk10")
        actions = (Action("buy", "Grandma", 10), Action("buy", "Farm", 3), Action("buy", "Cursor", 2))
        child, purchases = execute_shop_errand(gamestate, actions)
        self.assertEqual([purchase.quantity for purchase in purchases], [10, 3, 2])
        self.assertEqual(child.bank, 0)
        self.assertEqual(purchases[0].shop_actions, 3)
        with self.assertRaisesRegex(ValueError, "buys more"):
            execute_shop_errand(gamestate, tuple(reversed(actions)))
        with self.assertRaisesRegex(ValueError, "buys more"):
            execute_shop_errand(gamestate, (Action("buy", "Grandma", 7), Action("buy", "Farm", 5), Action("buy", "Cursor", 6)))
        self.assertEqual(gamestate.lifetime_cookies, 0)

    def test_bulk_search_keeps_distinct_executable_orders(self):
        gamestate = state("bulk10")
        gamestate.lifetime_cookies = 1_000
        cursor = next(e for e in initial_errands(gamestate) if e.purchase_order == (Action("buy", "Cursor", 10),))
        grandma = next(e for e in initial_errands(gamestate) if e.purchase_order == (Action("buy", "Grandma", 10),))
        cg = next(e for e in added_purchase_errands(gamestate, cursor) if e.purchase_order[-1] == Action("buy", "Grandma", 10))
        gc = next(e for e in added_purchase_errands(gamestate, grandma) if e.purchase_order[-1] == Action("buy", "Cursor", 10))
        self.assertEqual(cg.building_quantities, gc.building_quantities)
        self.assertNotEqual(cg, gc)
        self.assertIsNotNone(_evaluate(gamestate, 100_000, cg, 10))
        self.assertIsNotNone(_evaluate(gamestate, 100_000, gc, 10))

    def test_bulk_counts_clicks_not_copies(self):
        bulk = state("bulk10")
        single = state()
        child_bulk, purchases = execute_shop_errand(bulk, (Action("buy", "Cursor", 10),))
        child_single, _ = execute_shop_errand(single, (Action("buy", "Cursor"),) * 10)
        self.assertEqual(child_bulk.lifetime_cookies, child_single.lifetime_cookies)
        self.assertAlmostEqual(child_single.age - child_bulk.age, 9 * single.action_delay)
        self.assertEqual(purchases[0].shop_actions, 1)

    def test_sale_child_uses_refunds_and_all_action_delays(self):
        gamestate = state("single_with_sales")
        gamestate.building_counts["Cursor"] = 3
        gamestate.lifetime_cookies = 53
        grandma = next(e for e in initial_errands(gamestate) if e.building_quantities[1] == 1 and not e.upgrades)
        sale = next(e for e in added_purchase_errands(gamestate, grandma) if e.sales and e.sales[0] == 1)
        self.assertEqual(errand_price(gamestate, sale), 100 - gamestate.building_sale_refund("Cursor"))
        neighbor = _evaluate(gamestate, 10_000, sale, 2)
        self.assertIsNotNone(neighbor)
        self.assertEqual(neighbor.purchases[0].operation, "sell")
        self.assertEqual(neighbor.purchases[0].shop_actions, 4)  # sell + buy + two toggles
        self.assertEqual(neighbor.gamestate.building_counts["Cursor"], 2)
        pause = 0.8 + 4 * 0.2
        expected = (errand_price(gamestate, sale) + gamestate.hand_cps() * pause) / gamestate.cps()
        self.assertAlmostEqual(neighbor.acquisition_time, expected)

    def test_fully_sale_funded_improvement_has_finite_score(self):
        gamestate = state("single_with_sales")
        gamestate.errand_delay = gamestate.action_delay = 0
        quantities = tuple(1 if name == "Grandma" else 0 for name in gamestate.building_catalog)
        # A free production-improving transaction is eligible, even at zero elapsed time.
        gamestate.click_rate = 0
        gamestate.building_counts["Grandma"] = 1
        # Sell just one sufficiently expensive cursor and buy a cheap extra grandma.
        gamestate.building_counts["Cursor"] = 40
        sales = tuple(1 if name == "Cursor" else 0 for name in gamestate.building_catalog)
        neighbor = _evaluate(gamestate, 10_000, Errand(quantities, sales=sales), 2)
        self.assertEqual(neighbor.score, 0)

    def test_sale_surplus_is_banked_and_not_counted_as_production(self):
        gamestate = state("single_with_sales")
        gamestate.errand_delay = gamestate.action_delay = 0
        gamestate.building_counts["Farm"] = 1
        child, purchases = execute_shop_errand(gamestate, (Action("buy", "Cursor"), Action("sell", "Farm")))
        self.assertEqual(child.lifetime_cookies, 0)
        self.assertEqual(child.bank, gamestate.building_sale_refund("Farm") - 15)
        self.assertEqual(purchases[0].required_cookies, 0)
        next_child, next_purchases = execute_shop_errand(child, (Action("buy", "Grandma"),))
        self.assertEqual(next_child.lifetime_cookies, 0)
        self.assertEqual(next_purchases[0].required_cookies, 100)

    def test_sales_disabled_and_bulk_sales_validated(self):
        gamestate = state()
        gamestate.building_counts["Cursor"] = 13
        with self.assertRaisesRegex(ValueError, "disabled"):
            execute_shop_errand(gamestate, (Action("sell", "Cursor"),))
        gamestate = state("bulk10_with_sales")
        gamestate.building_counts["Cursor"] = 13
        with self.assertRaisesRegex(ValueError, "sale"):
            execute_shop_errand(gamestate, (Action("sell", "Cursor", 3),))
        child, purchases = execute_shop_errand(gamestate, (Action("sell", "Cursor", 13),))
        self.assertEqual([purchase.quantity for purchase in purchases], [10, 3])
        self.assertEqual(child.building_counts["Cursor"], 0)

    def test_bank_affects_bulk_affordability_and_search_identity(self):
        gamestate = state("bulk10")
        funded = gamestate.copy()
        funded.bank = 1_000
        self.assertNotEqual(inventory_key(gamestate), inventory_key(funded))
        with self.assertRaisesRegex(ValueError, "buys more"):
            execute_shop_errand(funded, (Action("buy", "Cursor"),))

    def test_bulk_upgrade_requires_prior_building_click(self):
        gamestate = state("bulk10")
        child, _ = execute_shop_errand(gamestate, (Action("buy", "Cursor", 10), Action("upgrade", "Reinforced index finger")))
        self.assertIn("Reinforced index finger", child.purchased_upgrades)
        with self.assertRaisesRegex(ValueError, "locked"):
            execute_shop_errand(gamestate, (Action("upgrade", "Reinforced index finger"), Action("buy", "Cursor", 10)))

    def test_generation_round_trip_matches_replay_for_all_profiles(self):
        for profile in ("single", "single_with_sales", "bulk10", "bulk10_with_sales"):
            for router in (greedy_route, beam_route):
                with self.subTest(profile=profile, router=router.__module__):
                    gamestate = state(profile)
                    options = {"queue_expansions": 8} if router is greedy_route else {
                        "beam_width": 3, "errand_search_width": 4,
                        "errand_queue_expansions": 8, "max_expansions": 20,
                    }
                    result = router(gamestate, 10_000, max_errand_actions=8, **options)
                    if router is beam_route:
                        self.assertLessEqual(result.final_gamestate.age, result.ruler_route.final_gamestate.age)
                    plan = plan_for(gamestate, action_errands(result))
                    with tempfile.TemporaryDirectory() as directory:
                        path = write_route(Path(directory) / "test.route", plan)
                        saved = load_route(path)
                    self.assertEqual(saved, plan)
                    replayed = execute_route(saved)
                    self.assertEqual(replayed.errands, result.errands)
                    self.assertEqual(replayed.final_gamestate.age, result.final_gamestate.age)

    def test_new_metadata_does_not_depend_on_profile_file(self):
        gamestate = state("bulk10")
        plan = plan_for(gamestate, ((Action("buy", "Cursor", 10),),))
        self.assertEqual(execute_route(plan).errands[0][0].quantity, 10)
        with tempfile.TemporaryDirectory() as directory:
            path = write_route(Path(directory) / "test.route", plan)
            path.write_text(path.read_text().replace("bulk_size = 10", "bulk_size = 100"))
            with self.assertRaisesRegex(ValueError, "bulk_size"):
                load_route(path)

    def test_target_reached_before_mixed_errand_is_not_overshot(self):
        initial = state("single_with_sales", "neverclick")
        plan = replace(
            plan_for(initial, ((Action("sell", "Cursor"), Action("buy", "Grandma")),)),
            initial_state="neverclick", target=16,
        )
        result = execute_route(plan)
        self.assertFalse(result.errands)
        self.assertEqual(result.final_gamestate.lifetime_cookies, 16)

    def test_cli_routes_accept_bulk_profile_and_replay_stored_settings(self):
        repository = Path(__file__).resolve().parents[1]
        for tool, options in (
            ("greedy_router.py", ["--queue-expansions", "8"]),
            ("beam_search_router.py", ["--beam-width", "3", "--errand-search-width", "4", "--errand-queue-expansions", "8", "--max-expansions", "20"]),
        ):
            output = subprocess.run(
                [sys.executable, f"tools/{tool}", "--category", "10k", "--player", "default_250_cps", "--errand-profile", "bulk10", "--verbose", *options],
                cwd=repository, text=True, capture_output=True, check=True,
            ).stdout
            self.assertIn("Errand profile: bulk10 (x10)", output)
            self.assertIn("Cursor ×10", output)
        plan = plan_for(state("bulk10"), ((Action("buy", "Cursor", 10),),))
        with tempfile.TemporaryDirectory() as directory:
            path = write_route(Path(directory) / "bulk.route", plan)
            output = subprocess.run(
                [sys.executable, "tools/route_replayer.py", str(path), "--verbose"],
                cwd=repository, text=True, capture_output=True, check=True,
            ).stdout
        self.assertIn("Cursor ×10", output)
        self.assertIn("recorded-settings", output)

    def test_errandifier_compiles_bulk_clicks_and_rejects_impossible_order(self):
        gamestate = state("bulk10")
        actions = (Action("buy", "Cursor"),) * 10
        errands = partition_contiguous_actions(gamestate, actions, state_width=2)
        self.assertEqual(errands, ((Action("buy", "Cursor", 10),),))
        funded = gamestate.copy()
        funded.bank = 1_000
        with self.assertRaisesRegex(ValueError, "No executable partition"):
            partition_contiguous_actions(funded, (Action("buy", "Cursor"),))

    def test_printout_has_explicit_bank_and_sale_mode_instructions(self):
        gamestate = state("single_with_sales")
        gamestate.errand_delay = gamestate.action_delay = 0
        gamestate.building_counts["Farm"] = 1
        child, first = execute_shop_errand(gamestate, (Action("sell", "Farm"), Action("buy", "Cursor")))
        child, second = execute_shop_errand(child, (Action("buy", "Grandma"),))
        result = RouteResult(gamestate, child.finish(10_000), (first, second))
        output = format_route(result, 10_000)
        self.assertIn("Switch to sell", output)
        self.assertIn("Switch to buy", output)
        self.assertIn("\n\n", output)
        self.assertNotIn("Current CpS", output)
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            table = LiveRouteTable(gamestate.lifetime_cookies)
            table.print_errand(first)
            table.print_errand(second)
            table.print_done(result.final_gamestate, 10_000)
        self.assertEqual(buffer.getvalue().rstrip("\n"), output)
        self.assertEqual(next(line for line in output.splitlines() if "Grandma #1" in line).split()[0], "100")


if __name__ == "__main__":
    unittest.main()

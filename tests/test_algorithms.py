import unittest

from src.algorithms import available_algorithms, get_algorithm
from src.algorithms.contiguous_errand_dp import partition_contiguous_actions
from src.algorithms.errand_queueing import (
    ErrandPlan,
    best_errand,
    effective_cost,
    errand_price,
    initial_errands,
    price_horizon,
    promising_errands,
)
from src.algorithms.fuzzy_astar import (
    SharedFuzzyHeuristic,
    find_route as find_fuzzy_astar_route,
)
from src.algorithms.scoring import age_score
from src.gamestate import Gamestate
from src.routes import RouteAction


class SyntheticState:
    def __init__(self, age, cps):
        self.age = age
        self._cps = cps

    def cps(self):
        return self._cps


class AlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.gamestate = Gamestate()
        self.gamestate.click_rate = 8

    def test_only_active_generators_are_exposed(self):
        self.assertEqual(
            available_algorithms(),
            ("errand_queueing", "fuzzy_astar", "singleton_errands"),
        )

    def test_age_score_uses_elapsed_acquisition_time(self):
        ancestor = SyntheticState(5, 10)
        faster = SyntheticState(12, 25)
        slower = SyntheticState(13, 25)

        self.assertLess(age_score(ancestor, faster), age_score(ancestor, slower))

    def test_dp_partition_can_start_with_one_multi_item_errand(self):
        gamestate = Gamestate("1.0466")
        gamestate.click_rate = 10
        gamestate.upgrades_allowed = False
        actions = (
            RouteAction("buy", "Cursor"),
            RouteAction("buy", "Farm"),
        )

        errands = partition_contiguous_actions(gamestate, actions)

        self.assertEqual(errands, (actions,))

    def test_dp_partition_respects_maximum_errand_size(self):
        actions = tuple(RouteAction("buy", "Cursor") for _ in range(3))

        errands = partition_contiguous_actions(
            self.gamestate,
            actions,
            max_errand_size=1,
        )

        self.assertEqual(errands, tuple((action,) for action in actions))

    def test_price_horizon_and_aggregate_errand_price(self):
        self.gamestate.lifetime_cookies = 10_000
        quantities = tuple(
            2 if name == "Farm" else 0
            for name in self.gamestate.building_catalog
        )

        self.assertEqual(price_horizon(self.gamestate, 2), 20_000)
        self.assertEqual(errand_price(self.gamestate, ErrandPlan(quantities)), 2_365)

    def test_locked_upgrade_seed_includes_prerequisite_buildings(self):
        plan = next(
            plan
            for plan in initial_errands(self.gamestate)
            if plan.upgrades == {"Forwards from grandma"}
        )
        grandma_index = list(self.gamestate.building_catalog).index("Grandma")

        self.assertEqual(plan.building_quantities[grandma_index], 1)
        self.assertEqual(plan.purchase_count, 2)

    def test_queue_finds_multi_purchase_errand(self):
        candidate = best_errand(self.gamestate, 100_000, queue_pops=100)

        self.assertGreater(len(candidate.purchases), 1)
        self.assertLessEqual(
            effective_cost(self.gamestate, candidate.gamestate),
            candidate.score,
        )

    def test_queue_returns_requested_number_of_promising_errands(self):
        candidates = promising_errands(
            self.gamestate,
            10_000,
            limit=3,
            queue_pops=20,
        )

        self.assertEqual(len(candidates), 3)
        self.assertEqual(
            list(map(lambda candidate: candidate.score, candidates)),
            sorted(candidate.score for candidate in candidates),
        )

    def test_fuzzy_astar_reaches_target_and_reports_search_stats(self):
        progress_updates = []
        result = find_fuzzy_astar_route(
            self.gamestate,
            1_000,
            feelers=3,
            queue_pops=20,
            fuzzy_scale=1.05,
            max_expansions=100,
            on_progress=progress_updates.append,
            progress_interval=0.000001,
        )

        self.assertEqual(result.final_gamestate.lifetime_cookies, 1_000)
        self.assertGreater(result.search_stats.expanded, 0)
        self.assertGreaterEqual(result.search_stats.elapsed_seconds, 0)
        self.assertTrue(result.errands)
        self.assertTrue(progress_updates)
        self.assertLessEqual(len(progress_updates[-1].frontier), 3)

    def test_fuzzy_heuristic_shares_geometric_checkpoint_tail(self):
        heuristic = SharedFuzzyHeuristic(self.gamestate, 20_000)

        remaining = heuristic(self.gamestate)

        self.assertGreater(remaining, 0)
        self.assertEqual(heuristic.checkpoints, (100, 1_000, 10_000))
        self.assertEqual(set(heuristic.shared_tails), {100})
        self.assertEqual(heuristic.route_evaluations, 2)

    def test_singleton_mode_never_groups(self):
        result = get_algorithm("singleton_errands")(
            self.gamestate,
            10_000,
        )

        self.assertTrue(result.errands)
        self.assertTrue(all(len(errand) == 1 for errand in result.errands))

    def test_route_generation_reaches_target_and_streams_errands(self):
        streamed = []

        result = get_algorithm("errand_queueing")(
            self.gamestate,
            10_000,
            on_errand=streamed.append,
        )

        self.assertEqual(result.final_gamestate.lifetime_cookies, 10_000)
        self.assertEqual(streamed, list(result.errands))


if __name__ == "__main__":
    unittest.main()

import unittest

from ccsr.errands.errandifier import partition_contiguous_actions
from ccsr.errands.generator import (
    Errand,
    acquisition_time,
    best_errand,
    errand_price,
    generate_neighbors,
    initial_errands,
    price_horizon,
)
from ccsr.errands.scoring import age_score
from ccsr.game.gamestate import Gamestate
from ccsr.routes import RouteAction
from ccsr.routing_algorithms.beam_search_router import find_route as find_beam
from ccsr.routing_algorithms.greedy_router import find_route as find_greedy
from ccsr.routing_algorithms.route_ruler import RouteRuler
from ccsr.routing_algorithms.parallel_neighbors import NeighborExecutor


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

    def test_age_score_uses_elapsed_acquisition_time(self):
        ancestor = SyntheticState(5, 10)
        faster = SyntheticState(12, 25)
        slower = SyntheticState(13, 25)

        self.assertLess(age_score(ancestor, faster), age_score(ancestor, slower))
        self.assertAlmostEqual(age_score(ancestor, faster), 35 / 3)

    def test_errand_price_and_item_count(self):
        self.gamestate.lifetime_cookies = 10_000
        quantities = tuple(
            2 if name == "Farm" else 0
            for name in self.gamestate.building_catalog
        )
        errand = Errand(quantities)

        self.assertEqual(errand.item_count, 2)
        self.assertEqual(price_horizon(self.gamestate, 2), 20_000)
        self.assertEqual(errand_price(self.gamestate, errand), 2_365)

    def test_upgrade_seed_can_include_prerequisite_buildings(self):
        errand = next(
            errand
            for errand in initial_errands(self.gamestate)
            if errand.upgrades == {"Forwards from grandma"}
        )
        grandma_index = list(self.gamestate.building_catalog).index("Grandma")

        self.assertEqual(errand.building_quantities[grandma_index], 1)
        self.assertEqual(errand.item_count, 2)

    def test_best_errand_can_group_purchases(self):
        neighbor = best_errand(self.gamestate, 100_000)

        self.assertGreater(len(neighbor.purchases), 1)
        self.assertLessEqual(
            acquisition_time(self.gamestate, neighbor.gamestate),
            neighbor.score,
        )

    def test_quickster_neighbors_are_single_item(self):
        self.gamestate.errand_delay = 0
        self.gamestate.item_delay = 0

        neighbors = generate_neighbors(
            self.gamestate,
            10_000,
            width=100,
            singleton_only=True,
        )

        self.assertTrue(neighbors)
        self.assertTrue(all(len(neighbor.purchases) == 1 for neighbor in neighbors))

    def test_greedy_supports_human_and_quickster_modes(self):
        human = find_greedy(self.gamestate, 1_000)
        quickster = find_greedy(self.gamestate, 1_000, for_quickster=True)

        self.assertTrue(human.errands)
        self.assertTrue(all(len(errand) == 1 for errand in quickster.errands))
        self.assertEqual(quickster.final_gamestate.errand_delay, 0)
        self.assertEqual(quickster.final_gamestate.item_delay, 0)

    def test_beam_generates_a_greedy_ruler_by_default(self):
        result = find_beam(self.gamestate, 1_000, beam_width=3)

        self.assertEqual(result.final_gamestate.lifetime_cookies, 1_000)
        self.assertTrue(result.search_stats.ruler_generated)
        self.assertTrue(result.ruler_route.errands)

    def test_beam_accepts_a_supplied_route_ruler(self):
        greedy = find_greedy(self.gamestate, 1_000)
        ruler = RouteRuler(greedy, scale=0.9)
        result = find_beam(
            self.gamestate,
            1_000,
            beam_width=3,
            ruler_route=greedy,
        )

        self.assertAlmostEqual(ruler(self.gamestate), greedy.final_gamestate.age * 0.9)
        self.assertFalse(result.search_stats.ruler_generated)

    def test_beam_supports_quickster_mode(self):
        result = find_beam(
            self.gamestate,
            1_000,
            beam_width=3,
            for_quickster=True,
        )

        self.assertTrue(all(len(errand) == 1 for errand in result.errands))
        self.assertEqual(result.final_gamestate.errand_delay, 0)

    def test_parallel_beam_preserves_serial_search_and_route(self):
        for bulk_size in (1, 10):
            with self.subTest(bulk_size=bulk_size):
                initial = Gamestate("2.031")
                initial.click_rate = 250
                initial.bulk_size = bulk_size
                initial.legacy_errands = False
                ruler = find_greedy(initial, 10_000, queue_expansions=10)
                options = dict(beam_width=5, errand_search_width=10,
                               errand_queue_expansions=20, max_expansions=100,
                               ruler_route=ruler)
                serial = find_beam(initial, 10_000, **options)
                parallel = find_beam(initial, 10_000, workers=2, **options)
                self.assertEqual(serial.errands, parallel.errands)
                self.assertEqual(serial.final_gamestate.age, parallel.final_gamestate.age)
                for field in ("expanded", "generated", "relaxed", "stale_skipped",
                              "heuristic_evaluations", "maximum_queue_size", "termination"):
                    self.assertEqual(getattr(serial.search_stats, field),
                                     getattr(parallel.search_stats, field))

    def test_parallel_beam_rejects_invalid_worker_count(self):
        with self.assertRaisesRegex(ValueError, "workers"):
            find_beam(self.gamestate, 1_000, workers=0)

    def test_parallel_neighbors_share_catalogs_without_mutating_parent(self):
        before = self.gamestate.copy()
        with NeighborExecutor(2, 10_000, dict(width=3, queue_expansions=10)) as executor:
            neighbors = executor.neighbors(self.gamestate)
        self.assertTrue(neighbors)
        for neighbor in neighbors:
            self.assertIs(neighbor.gamestate.building_catalog, self.gamestate.building_catalog)
            self.assertIs(neighbor.gamestate.upgrade_catalog, self.gamestate.upgrade_catalog)
        self.assertEqual(self.gamestate.building_counts, before.building_counts)
        self.assertEqual(self.gamestate.age, before.age)

    def test_dp_partition_respects_maximum_errand_size(self):
        actions = tuple(RouteAction("buy", "Cursor") for _ in range(3))

        errands = partition_contiguous_actions(
            self.gamestate,
            actions,
            max_errand_size=1,
        )

        self.assertEqual(errands, tuple((action,) for action in actions))


if __name__ == "__main__":
    unittest.main()

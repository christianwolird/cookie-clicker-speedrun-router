import unittest
from unittest.mock import patch

from src.algorithms import available_algorithms, get_algorithm
from src.algorithms.age_scoring import descendant_score as age_score
from src.algorithms.greedy import (
    candidate_descendants,
    price_cutoff,
    upgrade_descendant,
)
from src.algorithms.naive_scoring import descendant_score as naive_score
from src.data import Upgrade
from src.data.v2_031 import UPGRADES
from src.gamestate import Gamestate


class SyntheticGamestate:
    def __init__(self, age, lifetime_cookies, cps):
        self.age = age
        self.lifetime_cookies = lifetime_cookies
        self._cps = cps

    def cps(self):
        return self._cps


class AlgorithmTests(unittest.TestCase):
    def setUp(self):
        self.gamestate = Gamestate()
        self.gamestate.click_rate = 8

    def test_named_algorithms_share_the_route_interface(self):
        self.assertEqual(
            available_algorithms(),
            ("age_scoring", "naive_scoring"),
        )
        for name in available_algorithms():
            with self.subTest(name=name):
                route = get_algorithm(name).find_route(self.gamestate, 1_000)
                self.assertEqual(
                    route.final_gamestate.lifetime_cookies,
                    1_000,
                )
                self.assertTrue(route.purchases)

    def test_unknown_algorithm_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown algorithm"):
            get_algorithm("unknown")

    def test_age_score_matches_pairwise_ordering_formula(self):
        ancestor = SyntheticGamestate(0, 0, 10)
        better_first = SyntheticGamestate(10, 100, 20)
        worse_first = SyntheticGamestate(8, 80, 15)

        self.assertLess(
            age_score(ancestor, better_first),
            age_score(ancestor, worse_first),
        )

    def test_age_score_credits_faster_internal_descendant_order(self):
        ancestor = SyntheticGamestate(5, 0, 10)
        faster_descendant = SyntheticGamestate(12, 100, 25)
        slower_descendant = SyntheticGamestate(13, 100, 25)

        self.assertLess(
            age_score(ancestor, faster_descendant),
            age_score(ancestor, slower_descendant),
        )
        self.assertEqual(
            naive_score(ancestor, faster_descendant),
            naive_score(ancestor, slower_descendant),
        )

    def test_search_beats_buying_nothing(self):
        no_purchases = self.gamestate.finish(100_000)

        route = get_algorithm("age_scoring").find_route(
            self.gamestate,
            100_000,
        )

        self.assertLess(route.final_gamestate.age, no_purchases.age)
        self.assertEqual(
            route.final_gamestate.lifetime_cookies,
            100_000,
        )

    def test_search_reports_each_purchase_as_its_descendant_is_selected(self):
        purchases = []

        route = get_algorithm("age_scoring").find_route(
            self.gamestate,
            1_000,
            on_purchase=purchases.append,
        )

        self.assertEqual(purchases, list(route.purchases))

    def test_upgrades_can_be_removed_from_candidate_generation(self):
        self.gamestate.upgrades_allowed = False
        self.gamestate.purchase_building("Cursor")

        self.assertFalse(
            any(
                candidate.gamestate.purchased_upgrades
                for candidate in candidate_descendants(
                    self.gamestate,
                    age_score,
                )
            )
        )

    def test_price_cutoff_multiplier_is_configurable(self):
        self.gamestate.lifetime_cookies = 10_000

        self.assertEqual(price_cutoff(self.gamestate, 2.0), 20_000)
        self.assertEqual(price_cutoff(self.gamestate, 4.0), 40_000)
        self.assertEqual(price_cutoff(self.gamestate, 0.01), 1_000)

    def test_candidate_descendants_include_locked_upgrade_prerequisites(self):
        candidate = next(
            candidate
            for candidate in candidate_descendants(self.gamestate, age_score)
            if candidate.gamestate.last_purchase.display_item
            == "Forwards from grandma"
        )
        descendant = candidate.gamestate

        self.assertEqual(descendant.building_counts["Grandma"], 1)
        self.assertIn(
            "Forwards from grandma",
            descendant.purchased_upgrades,
        )
        self.assertEqual(
            [purchase.display_item for purchase in candidate.purchases],
            ["Grandma #1", "Forwards from grandma"],
        )

    def test_upgrade_cutoff_does_not_exclude_mixed_prerequisites(self):
        self.gamestate.lifetime_cookies = 30_000
        cutoff = price_cutoff(self.gamestate, 2.0)
        candidate = next(
            candidate
            for candidate in candidate_descendants(self.gamestate, age_score)
            if candidate.gamestate.last_purchase.display_item
            == "Farmer grandmas"
        )
        descendant = candidate.gamestate

        self.assertEqual(cutoff, 60_000)
        self.assertGreater(
            descendant.lifetime_cookies
            - self.gamestate.lifetime_cookies,
            cutoff,
        )
        self.assertEqual(descendant.building_counts["Grandma"], 1)
        self.assertEqual(descendant.building_counts["Farm"], 15)
        self.assertIn("Farmer grandmas", descendant.purchased_upgrades)
        self.assertEqual(candidate.purchases[0].display_item, "Grandma #1")

    def test_mixed_prerequisite_errands_follow_the_selected_score(self):
        upgrade = Upgrade(1, (("Grandma", 15), ("Farm", 5)))

        with patch.dict(UPGRADES, {"Test mixed": upgrade}):
            candidate = upgrade_descendant(
                self.gamestate,
                "Test mixed",
                age_score,
            )

        self.assertEqual(
            [purchase.display_item for purchase in candidate.purchases],
            [
                "Grandma #1",
                "Grandma #2",
                "Grandma #3",
                "Grandma #4",
                "Grandma #5",
                "Farm #1",
                "Farm #2",
                "Grandma #6",
                "Farm #3",
                "Grandma #7",
                "Farm #4",
                "Grandma #8",
                "Farm #5",
                "Grandma #9",
                "Grandma #10",
                "Grandma #11",
                "Grandma #12",
                "Grandma #13",
                "Grandma #14",
                "Grandma #15",
                "Test mixed",
            ],
        )


if __name__ == "__main__":
    unittest.main()

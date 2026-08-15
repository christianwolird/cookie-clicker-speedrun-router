import unittest
from unittest.mock import patch

from src.data import Upgrade
from src.data.v2_031 import UPGRADES
from src.game import Game


class GameTests(unittest.TestCase):
    def test_default_player_settings(self):
        game = Game()

        self.assertEqual(game.version, "2.031")
        self.assertEqual(game.clickrate, 10)
        self.assertEqual(game.purchase_delay, 0.5)

    def test_version_selects_the_complete_game_catalog(self):
        current = Game("2.031")
        legacy = Game("1.0466")

        self.assertEqual(current.building_price("Farm"), 1_100)
        self.assertEqual(legacy.building_price("Farm"), 500)
        self.assertIn("Bank", current.num_buildings)
        self.assertNotIn("Bank", legacy.num_buildings)
        self.assertIn("Cookie", legacy.upgrade_families)

    def test_every_upgrade_has_a_serializable_family_and_tier(self):
        for version in ("1.0466", "2.031"):
            with self.subTest(version=version):
                game = Game(version)
                self.assertEqual(set(game.upgrade_info), set(game.upgrade_routes))

    def test_unknown_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown game version"):
            Game("not-a-version")

    def test_neverclick_initial_state(self):
        game = Game()

        game.initialize_neverclick()

        self.assertEqual(game.clickrate, 0)
        self.assertEqual(game.cookies, 15)
        self.assertEqual(game.handmade_cookies, 15)
        self.assertEqual(game.num_buildings["Cursor"], 1)
        self.assertIsNone(game.last_purchase)
        self.assertIn("Wake and bake", game.achievements)
        self.assertIn("Click", game.achievements)

    def test_upgrades_can_be_disabled(self):
        game = Game()
        game.allow_upgrades = False
        game.purchase_building("Cursor")

        with self.assertRaisesRegex(ValueError, "disabled"):
            game.purchase_upgrade("Reinforced index finger")

        self.assertFalse(any(child.game.upgrades for child in game.children()))

    def setUp(self):
        self.game = Game()
        self.game.clickrate = 8

    def test_building_prices_are_rounded_up_like_the_game(self):
        self.assertEqual(self.game.building_price("Cursor"), 15)
        self.game.num_buildings["Cursor"] = 1
        self.assertEqual(self.game.building_price("Cursor"), 18)

    def test_copy_keeps_only_the_purchase_that_produced_the_state(self):
        self.game.price_cutoff_multiplier = 4.0
        self.game.purchase_building("Cursor")
        child = self.game.copy()
        child.purchase_building("Grandma")

        self.assertEqual(self.game.last_purchase.display_item, "Cursor #1")
        self.assertEqual(child.last_purchase.display_item, "Grandma #1")
        self.assertEqual(self.game.num_buildings["Grandma"], 0)
        self.assertEqual(child.last_purchase.age, child.age)
        self.assertEqual(child.last_purchase.cookies, child.cookies)
        self.assertEqual(child.price_cutoff_multiplier, 4.0)
        self.assertEqual(child.version, self.game.version)
        self.assertFalse(hasattr(child, "history"))
        self.assertFalse(hasattr(child, "purchase_log"))

    def test_price_cutoff_multiplier_is_configurable(self):
        self.game.cookies = 10_000

        self.assertEqual(self.game.price_cutoff(), 20_000)
        self.game.price_cutoff_multiplier = 4.0
        self.assertEqual(self.game.price_cutoff(), 40_000)
        self.game.price_cutoff_multiplier = 0.01
        self.assertEqual(self.game.price_cutoff(), 1_000)

    def test_cursor_upgrade_affects_clicks_and_cursors(self):
        self.game.purchase_building("Cursor")
        self.game.purchase_upgrade("Reinforced index finger")

        self.assertAlmostEqual(self.game.cookies_per_click(), 2)
        self.assertAlmostEqual(self.game.building_cps(), 0.2)
        self.assertAlmostEqual(self.game.cps(), 16.2)

    def test_locked_upgrade_purchase_is_atomic(self):
        before = self.game.copy()

        with self.assertRaises(ValueError):
            self.game.purchase_upgrade("Thousand fingers")

        self.assertEqual(self.game.age, before.age)
        self.assertEqual(self.game.cookies, before.cookies)
        self.assertEqual(self.game.last_purchase, before.last_purchase)

    def test_achievements_are_automatic(self):
        self.game.cookies = 100_000
        self.game.handmade_cookies = 1_000
        self.game.num_buildings["Grandma"] = 1
        self.game.update_achievements()

        self.assertIn("Wake and bake", self.game.achievements)
        self.assertIn("Making some dough", self.game.achievements)
        self.assertIn("So baked right now", self.game.achievements)
        self.assertIn("Clicktastic", self.game.achievements)
        self.assertIn("Grandma's cookies", self.game.achievements)

    def test_kitten_uses_achievement_count_as_milk(self):
        self.game.num_buildings["Grandma"] = 1
        self.game.achievements = {f"achievement {number}" for number in range(13)}
        self.game.cookies = 1_000_000
        self.game.purchase_upgrade("Kitten helpers")

        expected = 1 + (len(self.game.achievements) / 25) * 0.1
        self.assertAlmostEqual(self.game.building_cps(), expected)

    def test_children_bundle_locked_upgrade_prerequisites(self):
        candidate = next(
            candidate
            for candidate in self.game.children()
            if candidate.game.last_purchase.display_item == "Forwards from grandma"
        )
        child = candidate.game

        self.assertEqual(child.num_buildings["Grandma"], 1)
        self.assertIn("Forwards from grandma", child.upgrades)
        self.assertEqual(
            [purchase.display_item for purchase in candidate.purchases],
            ["Grandma #1", "Forwards from grandma"],
        )

    def test_upgrade_cutoff_does_not_exclude_mixed_prerequisites(self):
        self.game.cookies = 30_000
        cutoff = self.game.price_cutoff()
        candidate = next(
            candidate
            for candidate in self.game.children()
            if candidate.game.last_purchase.display_item == "Farmer grandmas"
        )
        child = candidate.game

        self.assertEqual(cutoff, 60_000)
        self.assertGreater(child.cookies - self.game.cookies, cutoff)
        self.assertEqual(child.num_buildings["Grandma"], 1)
        self.assertEqual(child.num_buildings["Farm"], 15)
        self.assertIn("Farmer grandmas", child.upgrades)
        self.assertEqual(candidate.purchases[0].display_item, "Grandma #1")

    def test_mixed_prerequisites_are_interleaved_by_purchase_score(self):
        upgrade = Upgrade(1, (("Grandma", 15), ("Farm", 5)))

        with patch.dict(UPGRADES, {"Test mixed": upgrade}):
            candidate = self.game._with_upgrade_prerequisites("Test mixed")

        self.assertEqual(
            [purchase.display_item for purchase in candidate.purchases],
            [
                "Grandma #1",
                "Grandma #2",
                "Grandma #3",
                "Grandma #4",
                "Grandma #5",
                "Grandma #6",
                "Farm #1",
                "Farm #2",
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

import unittest

from src.gamestate import Gamestate


class GamestateTests(unittest.TestCase):
    def test_default_player_settings(self):
        gamestate = Gamestate()

        self.assertEqual(gamestate.version, "2.031")
        self.assertEqual(gamestate.click_rate, 10)
        self.assertEqual(gamestate.errand_duration, 1.0)
        self.assertEqual(gamestate.purchase_click_rate, 5.0)
        self.assertEqual(gamestate.errand_pause(), 1.2)

    def test_single_purchase_includes_trip_and_shop_click_downtime(self):
        gamestate = Gamestate()

        gamestate.purchase_building("Cursor")

        # With no automatic CpS, earning 15 cookies takes 1.5 seconds of
        # clicking plus the 1.0-second trip and one 0.2-second shop click.
        self.assertAlmostEqual(gamestate.age, 2.7)
        self.assertAlmostEqual(gamestate.handmade_cookies, 15.0)

    def test_version_selects_the_complete_game_catalog(self):
        current = Gamestate("2.031")
        legacy = Gamestate("1.0466")

        self.assertEqual(current.building_price("Farm"), 1_100)
        self.assertEqual(legacy.building_price("Farm"), 500)
        self.assertIn("Bank", current.building_counts)
        self.assertNotIn("Bank", legacy.building_counts)
        self.assertIn("Oatmeal raisin cookies", legacy.upgrade_catalog)

    def test_upgrade_catalogs_use_proper_version_specific_names(self):
        for version in ("1.0466", "2.031"):
            with self.subTest(version=version):
                gamestate = Gamestate(version)
                self.assertIn(
                    "Reinforced index finger",
                    gamestate.upgrade_catalog,
                )
                self.assertFalse(
                    any(
                        "upgrade #" in name
                        for name in gamestate.upgrade_catalog
                    )
                )

    def test_unknown_version_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown game version"):
            Gamestate("not-a-version")

    def test_neverclick_initial_state(self):
        gamestate = Gamestate()

        gamestate.initialize_neverclick()

        self.assertEqual(gamestate.click_rate, 0)
        self.assertEqual(gamestate.lifetime_cookies, 15)
        self.assertEqual(gamestate.handmade_cookies, 15)
        self.assertEqual(gamestate.building_counts["Cursor"], 1)
        self.assertIsNone(gamestate.last_purchase)
        self.assertIn("Wake and bake", gamestate.earned_achievements)
        self.assertIn("Click", gamestate.earned_achievements)

    def test_upgrades_can_be_disabled(self):
        gamestate = Gamestate()
        gamestate.upgrades_allowed = False
        gamestate.purchase_building("Cursor")

        with self.assertRaisesRegex(ValueError, "disabled"):
            gamestate.purchase_upgrade("Reinforced index finger")

    def setUp(self):
        self.gamestate = Gamestate()
        self.gamestate.click_rate = 8

    def test_building_prices_are_rounded_up_like_the_game(self):
        self.assertEqual(self.gamestate.building_price("Cursor"), 15)
        self.gamestate.building_counts["Cursor"] = 1
        self.assertEqual(self.gamestate.building_price("Cursor"), 18)

    def test_selling_refunds_one_quarter_of_the_purchase_price(self):
        self.gamestate.purchase_building("Cursor")

        self.gamestate.sell_building("Cursor")

        self.assertEqual(self.gamestate.sale_credit, 3)
        self.assertEqual(self.gamestate.building_counts["Cursor"], 0)

    def test_copy_keeps_only_the_purchase_that_produced_the_state(self):
        self.gamestate.purchase_building("Cursor")
        child = self.gamestate.copy()
        child.purchase_building("Grandma")

        self.assertEqual(self.gamestate.last_purchase.display_item, "Cursor #1")
        self.assertEqual(child.last_purchase.display_item, "Grandma #1")
        self.assertEqual(self.gamestate.building_counts["Grandma"], 0)
        self.assertEqual(child.last_purchase.age, child.age)
        self.assertEqual(
            child.last_purchase.lifetime_cookies,
            child.lifetime_cookies,
        )
        self.assertEqual(child.version, self.gamestate.version)
        self.assertEqual(
            child.purchase_click_rate,
            self.gamestate.purchase_click_rate,
        )
        self.assertFalse(hasattr(child, "history"))
        self.assertFalse(hasattr(child, "purchase_log"))

    def test_cursor_upgrade_affects_clicks_and_cursors(self):
        self.gamestate.purchase_building("Cursor")
        self.gamestate.purchase_upgrade("Reinforced index finger")

        self.assertAlmostEqual(self.gamestate.cookies_per_click(), 2)
        self.assertAlmostEqual(self.gamestate.automatic_cps(), 0.2)
        self.assertAlmostEqual(self.gamestate.cps(), 16.2)

    def test_locked_upgrade_purchase_is_atomic(self):
        before = self.gamestate.copy()

        with self.assertRaises(ValueError):
            self.gamestate.purchase_upgrade("Thousand fingers")

        self.assertEqual(self.gamestate.age, before.age)
        self.assertEqual(
            self.gamestate.lifetime_cookies,
            before.lifetime_cookies,
        )
        self.assertEqual(self.gamestate.last_purchase, before.last_purchase)

    def test_achievements_are_automatic(self):
        self.gamestate.lifetime_cookies = 100_000
        self.gamestate.handmade_cookies = 1_000
        self.gamestate.building_counts["Grandma"] = 1
        self.gamestate.update_achievements()

        self.assertIn("Wake and bake", self.gamestate.earned_achievements)
        self.assertIn("Making some dough", self.gamestate.earned_achievements)
        self.assertIn(
            "So baked right now",
            self.gamestate.earned_achievements,
        )
        self.assertIn("Clicktastic", self.gamestate.earned_achievements)
        self.assertIn(
            "Grandma's cookies",
            self.gamestate.earned_achievements,
        )

    def test_kitten_uses_achievement_count_as_milk(self):
        self.gamestate.building_counts["Grandma"] = 1
        self.gamestate.earned_achievements = {
            f"achievement {number}" for number in range(13)
        }
        self.gamestate.lifetime_cookies = 1_000_000
        self.gamestate.purchase_upgrade("Kitten helpers")

        expected = 1 + (
            len(self.gamestate.earned_achievements) / 25
        ) * 0.1
        self.assertAlmostEqual(self.gamestate.automatic_cps(), expected)


if __name__ == "__main__":
    unittest.main()

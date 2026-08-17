import unittest

from src.gamestate import Gamestate


class GamestateTests(unittest.TestCase):
    def test_default_errand_timing(self):
        gamestate = Gamestate()

        purchases = gamestate.purchase_errand({"Cursor": 2})

        self.assertEqual(len(purchases), 2)
        self.assertEqual(gamestate.lifetime_cookies, 33)
        self.assertAlmostEqual(gamestate.age, 4.5)
        self.assertEqual(gamestate.errand_pause(), 1.2)

    def test_distinct_purchase_types_add_shop_time(self):
        gamestate = Gamestate()

        gamestate.purchase_errand({"Cursor": 1, "Grandma": 1})

        # 115 cookies at 10 hand CpS, plus 1 second of travel and two
        # purchase-type clicks at 5 per second.
        self.assertAlmostEqual(gamestate.age, 12.9)

    def test_building_can_unlock_upgrade_in_same_unordered_errand(self):
        gamestate = Gamestate()

        purchases = gamestate.purchase_errand(
            {"Grandma": 1},
            {"Forwards from grandma"},
        )

        self.assertEqual(gamestate.building_counts["Grandma"], 1)
        self.assertIn("Forwards from grandma", gamestate.purchased_upgrades)
        self.assertEqual(
            {purchase.item for purchase in purchases},
            {"Grandma", "Forwards from grandma"},
        )

    def test_failed_purchase_is_atomic(self):
        gamestate = Gamestate()
        before = gamestate.copy()

        with self.assertRaisesRegex(ValueError, "locked"):
            gamestate.purchase_upgrade("Thousand fingers")

        self.assertEqual(gamestate.age, before.age)
        self.assertEqual(gamestate.lifetime_cookies, before.lifetime_cookies)
        self.assertEqual(gamestate.building_counts, before.building_counts)

    def test_copy_has_independent_inventory_and_no_history(self):
        gamestate = Gamestate()
        child = gamestate.copy()
        child.purchase_building("Cursor")

        self.assertEqual(gamestate.building_counts["Cursor"], 0)
        self.assertEqual(child.building_counts["Cursor"], 1)
        self.assertFalse(hasattr(child, "history"))
        self.assertFalse(hasattr(child, "purchase_log"))
        self.assertFalse(hasattr(child, "last_purchase"))
        self.assertFalse(hasattr(child, "last_errand"))

    def test_neverclick_ignores_hand_pause(self):
        normal = Gamestate()
        normal.initialize_neverclick()
        long_pause = normal.copy()
        long_pause.errand_duration = 100
        long_pause.purchase_click_rate = 0.01

        normal.purchase_building("Cursor")
        long_pause.purchase_building("Cursor")

        self.assertEqual(normal.hand_cps(), 0)
        self.assertAlmostEqual(normal.age, long_pause.age)

    def test_versions_select_complete_catalogs(self):
        current = Gamestate("2.031")
        legacy = Gamestate("1.0466")

        self.assertEqual(current.building_price("Farm"), 1_100)
        self.assertEqual(legacy.building_price("Farm"), 500)
        self.assertIn("Bank", current.building_catalog)
        self.assertNotIn("Bank", legacy.building_catalog)
        self.assertIn("Oatmeal raisin cookies", legacy.upgrade_catalog)

    def test_cursor_upgrade_affects_clicks_and_cursors(self):
        gamestate = Gamestate()
        gamestate.click_rate = 8
        gamestate.purchase_building("Cursor")
        gamestate.purchase_upgrade("Reinforced index finger")

        self.assertAlmostEqual(gamestate.cookies_per_click(), 2)
        self.assertAlmostEqual(gamestate.automatic_cps(), 0.2)
        self.assertAlmostEqual(gamestate.cps(), 16.2)

    def test_sale_refund_uses_previous_purchase_price(self):
        gamestate = Gamestate()
        gamestate.purchase_building("Cursor")

        purchases = gamestate.sell_building("Cursor")

        self.assertEqual(gamestate.sale_credit, 3)
        self.assertEqual(gamestate.building_counts["Cursor"], 0)
        self.assertEqual(purchases[0].operation, "sell")

    def test_achievements_feed_kitten_milk(self):
        gamestate = Gamestate()
        gamestate.building_counts["Grandma"] = 1
        gamestate.earned_achievements = {
            f"achievement {number}" for number in range(13)
        }
        gamestate.lifetime_cookies = 1_000_000

        gamestate.purchase_upgrade("Kitten helpers")

        expected = 1 + len(gamestate.earned_achievements) / 25 * 0.1
        self.assertAlmostEqual(gamestate.automatic_cps(), expected)


if __name__ == "__main__":
    unittest.main()

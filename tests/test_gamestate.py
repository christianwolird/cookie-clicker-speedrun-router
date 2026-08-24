import unittest

from ccsr.config.achievement_curves import AchievementCurve
from ccsr.game.gamestate import Gamestate


class GamestateTests(unittest.TestCase):
    def test_default_errand_timing_counts_every_item(self):
        gamestate = Gamestate()

        purchases = gamestate.purchase_errand({"Cursor": 3, "Grandma": 2})

        self.assertEqual(len(purchases), 5)
        self.assertEqual(gamestate.lifetime_cookies, 268)
        self.assertAlmostEqual(gamestate.age, 28.8)
        self.assertEqual(gamestate.errand_pause(5), 2.0)

    def test_achievement_curve_controls_kitten_multiplier(self):
        curve = AchievementCurve("test", (0, 100), (0, 10))
        gamestate = Gamestate("2.031", curve)
        gamestate.building_counts["Grandma"] = 1
        gamestate.purchased_upgrades.add("Kitten helpers")
        gamestate.lifetime_cookies = 100

        self.assertEqual(gamestate.achievement_count(), 10)
        self.assertAlmostEqual(gamestate.automatic_cps(), 1.04)

    def test_achievements_do_not_gate_kitten_unlocks(self):
        gamestate = Gamestate("2.031")
        gamestate.lifetime_cookies = 9_000_000

        gamestate.purchase_upgrade("Kitten helpers")

        self.assertIn("Kitten helpers", gamestate.purchased_upgrades)

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

    def test_copy_has_independent_inventory(self):
        gamestate = Gamestate()
        child = gamestate.copy()
        child.purchase_building("Cursor")

        self.assertEqual(gamestate.building_counts["Cursor"], 0)
        self.assertEqual(child.building_counts["Cursor"], 1)

    def test_neverclick_ignores_hand_pause(self):
        normal = Gamestate()
        normal.initialize_neverclick()
        long_pause = normal.copy()
        long_pause.errand_delay = 100
        long_pause.item_delay = 100

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

    def test_sale_refund_uses_previous_purchase_price(self):
        gamestate = Gamestate()
        gamestate.purchase_building("Cursor")

        purchases = gamestate.sell_building("Cursor")

        self.assertEqual(gamestate.sale_credit, 3)
        self.assertEqual(purchases[0].operation, "sell")


if __name__ == "__main__":
    unittest.main()

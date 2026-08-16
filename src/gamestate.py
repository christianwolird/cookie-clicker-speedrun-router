from dataclasses import dataclass
from math import ceil, floor

from .data import DEFAULT_VERSION, get_version_data


DEFAULT_CLICK_RATE = 10.0
DEFAULT_ERRAND_DURATION = 1.0
DEFAULT_PURCHASE_CLICK_RATE = 5.0


@dataclass(frozen=True, slots=True)
class Purchase:
    operation: str
    item: str
    age: float
    lifetime_cookies: float
    label: str | None = None

    @property
    def display_item(self):
        return self.label or self.item

    def route_action(self):
        return f"{self.operation} {self.item}"


class Gamestate:
    """A snapshot of a fresh Cookie Clicker ascension.

    ``version`` selects one complete data catalog for the lifetime of the run.
    ``lifetime_cookies`` is total cookies baked, not the current bank; the
    current model assumes the bank is empty at each snapshot. Until errands can
    contain multiple purchases, every purchase is treated as a separate errand.
    Hand-clicking pauses for ``errand_duration`` seconds of travel plus one
    shop click at ``purchase_click_rate`` while buildings continue producing.
    """

    def __init__(self, version=DEFAULT_VERSION):
        version_data = get_version_data(version)
        self.version = version_data.VERSION
        self.building_catalog = version_data.BUILDINGS
        self.upgrade_catalog = version_data.UPGRADES
        self.achievement_catalog = version_data.ACHIEVEMENTS

        self.click_rate = DEFAULT_CLICK_RATE
        self.errand_duration = DEFAULT_ERRAND_DURATION
        self.purchase_click_rate = DEFAULT_PURCHASE_CLICK_RATE
        self.upgrades_allowed = True

        self.age = 0.0
        self.lifetime_cookies = 0.0
        self.handmade_cookies = 0.0
        self.sale_credit = 0.0

        self.building_counts = {name: 0 for name in self.building_catalog}
        self.purchased_upgrades = set()
        self.earned_achievements = set()
        self.last_purchase = None
        self._automatic_cps_cache = None

    def copy(self):
        copied_gamestate = Gamestate(self.version)
        copied_gamestate.click_rate = self.click_rate
        copied_gamestate.errand_duration = self.errand_duration
        copied_gamestate.purchase_click_rate = self.purchase_click_rate
        copied_gamestate.upgrades_allowed = self.upgrades_allowed
        copied_gamestate.age = self.age
        copied_gamestate.lifetime_cookies = self.lifetime_cookies
        copied_gamestate.handmade_cookies = self.handmade_cookies
        copied_gamestate.sale_credit = self.sale_credit
        copied_gamestate.building_counts = dict(self.building_counts)
        copied_gamestate.purchased_upgrades = set(self.purchased_upgrades)
        copied_gamestate.earned_achievements = set(
            self.earned_achievements
        )
        copied_gamestate.last_purchase = self.last_purchase
        copied_gamestate._automatic_cps_cache = self._automatic_cps_cache
        return copied_gamestate

    def initialize_neverclick(self):
        """Start immediately after the category's 15 clicks and first Cursor."""
        self.click_rate = 0.0
        self.lifetime_cookies = 15.0
        self.handmade_cookies = 15.0
        self.building_counts["Cursor"] = 1
        self._automatic_cps_cache = None
        self.update_achievements()

    def __str__(self):
        return (
            f"Age: {self.age:.3f} -- Cookies baked: {self.lifetime_cookies:.0f} "
            f"-- CpS: {self.cps():.3f}"
        )

    def __repr__(self):
        return str(self)

    def building_price(self, name):
        base_price = self.building_catalog[name].base_price
        return ceil(base_price * 1.15 ** self.building_counts[name])

    def _cursor_bonus(self):
        bonus = sum(
            self.upgrade_catalog[name].finger_add
            for name in self.purchased_upgrades
            if name in self.upgrade_catalog
        )
        non_cursors = (
            sum(self.building_counts.values()) - self.building_counts["Cursor"]
        )
        return bonus * non_cursors

    def _cursor_multiplier(self):
        multiplier = 1.0
        for name in self.purchased_upgrades:
            if name in self.upgrade_catalog:
                multiplier *= self.upgrade_catalog[name].cursor_multiplier
        return multiplier

    def _building_multiplier(self, name):
        multiplier = 1.0
        for upgrade_name in self.purchased_upgrades:
            upgrade = self.upgrade_catalog[upgrade_name]
            if upgrade.building == name:
                multiplier *= 2
            if upgrade.grandma_synergy:
                if name == "Grandma":
                    multiplier *= 2
                elif name == upgrade.grandma_synergy:
                    building_id = list(self.building_catalog).index(name)
                    grandma_bonus = (
                        self.building_counts["Grandma"]
                        * 0.01
                        / (building_id - 1)
                    )
                    multiplier *= 1 + grandma_bonus
        return multiplier

    def automatic_cps(self):
        if self._automatic_cps_cache is not None:
            return self._automatic_cps_cache

        total = 0.0
        for name, number in self.building_counts.items():
            per_building = self.building_catalog[name].base_cps
            if name == "Cursor":
                per_building = (
                    per_building * self._cursor_multiplier() + self._cursor_bonus()
                )
            total += number * per_building * self._building_multiplier(name)

        for name in self.purchased_upgrades:
            total *= self.upgrade_catalog[name].production_multiplier

        milk = len(self.earned_achievements) / 25
        for name in self.purchased_upgrades:
            kitten = self.upgrade_catalog[name].kitten_coefficient
            if kitten:
                total *= 1 + milk * kitten
        self._automatic_cps_cache = total
        return self._automatic_cps_cache

    def cookies_per_click(self):
        power = self._cursor_multiplier() + self._cursor_bonus()
        for name in self.purchased_upgrades:
            power += (
                self.upgrade_catalog[name].mouse_cps_fraction
                * self.automatic_cps()
            )
        return power

    def hand_cps(self):
        return self.click_rate * self.cookies_per_click()

    def cps(self):
        return self.automatic_cps() + self.hand_cps()

    def _achievement_value(self, achievement):
        if achievement.kind == "cookies":
            return self.lifetime_cookies
        if achievement.kind == "cps":
            return self.automatic_cps()
        if achievement.kind == "handmade":
            return self.handmade_cookies
        if achievement.kind == "building":
            return self.building_counts[achievement.building]
        if achievement.kind == "buildings":
            return sum(self.building_counts.values())
        if achievement.kind == "upgrades":
            return len(self.purchased_upgrades)
        raise ValueError(f"Unknown achievement kind: {achievement.kind}")

    def update_achievements(self):
        # A newly earned achievement can improve a kitten, which can earn the
        # next CpS achievement, so repeat until milk and CpS settle.
        changed = True
        while changed:
            changed = False
            for name, achievement in self.achievement_catalog.items():
                if name not in self.earned_achievements and (
                    self._achievement_value(achievement) >= achievement.threshold
                ):
                    self.earned_achievements.add(name)
                    if any(
                        self.upgrade_catalog[item].kitten_coefficient
                        for item in self.purchased_upgrades
                    ):
                        self._automatic_cps_cache = None
                    changed = True

    def errand_pause(self, purchase_count=1):
        """Return hand-clicking downtime for one errand.

        Route actions are not grouped into errands yet, so callers currently
        pass the default one purchase. Keeping the count explicit makes the
        timing rule ready for multi-purchase errands without storing player
        timing assumptions in route files.
        """
        if purchase_count < 1:
            raise ValueError("purchase_count must be at least one")
        if self.purchase_click_rate <= 0:
            raise ValueError("purchase_click_rate must be greater than zero")
        return self.errand_duration + purchase_count / self.purchase_click_rate

    def _advance_to_purchase(self, price):
        credit = min(price, self.sale_credit)
        self.sale_credit -= credit
        price -= credit
        if price == 0:
            return

        total_cps = self.cps()
        if total_cps <= 0:
            raise ValueError("Cannot earn cookies with zero CpS")

        hand_cps = self.hand_cps()
        # Each purchase is currently its own errand: one fixed trip plus one
        # shop click. Hand-clicking stops for that whole pause while buildings
        # keep baking. Solving (auto + hand) * (T - pause) + auto * pause
        # = price gives T = (price + hand * pause) / total CpS.
        pause = self.errand_pause()
        duration = (price + hand_cps * pause) / total_cps
        active_clicking = max(0.0, duration - pause)
        self.handmade_cookies += hand_cps * active_clicking
        self.age += duration
        self.lifetime_cookies += price
        self.update_achievements()

    def purchase_building(self, name):
        price = self.building_price(name)
        self._advance_to_purchase(price)
        self.building_counts[name] += 1
        self._automatic_cps_cache = None
        self.last_purchase = Purchase(
            "buy",
            name,
            self.age,
            self.lifetime_cookies,
            label=f"{name} #{self.building_counts[name]}",
        )
        self.update_achievements()

    def sell_building(self, name):
        if self.building_counts[name] <= 0:
            raise ValueError(f"Cannot sell an unowned building: {name}")

        refund = floor(self.building_price(name) / 4)
        self.building_counts[name] -= 1
        self.sale_credit += refund
        self._automatic_cps_cache = None
        self.last_purchase = Purchase(
            "sell",
            name,
            self.age,
            self.lifetime_cookies,
            label=f"Sell {name} #{self.building_counts[name] + 1}",
        )
        self.update_achievements()

    def upgrade_unlocked(self, name):
        upgrade = self.upgrade_catalog[name]
        return (
            all(
                self.building_counts[building] >= number
                for building, number in upgrade.requirements
            )
            and self.lifetime_cookies >= upgrade.cookies_required
            and self.handmade_cookies >= upgrade.handmade_required
            and len(self.earned_achievements) >= upgrade.achievements_required
        )

    def purchase_upgrade(self, name):
        if not self.upgrades_allowed:
            raise ValueError("Upgrades are disabled")
        if name in self.purchased_upgrades:
            raise ValueError(f"Upgrade already purchased: {name}")

        upgrade = self.upgrade_catalog[name]
        paid = self.copy()
        paid._advance_to_purchase(upgrade.price)
        if not paid.upgrade_unlocked(name):
            raise ValueError(f"Upgrade is still locked: {name}")

        self.age = paid.age
        self.lifetime_cookies = paid.lifetime_cookies
        self.handmade_cookies = paid.handmade_cookies
        self.earned_achievements = paid.earned_achievements
        self.purchased_upgrades.add(name)
        self._automatic_cps_cache = None
        self.last_purchase = Purchase(
            "upgrade",
            name,
            self.age,
            self.lifetime_cookies,
        )
        self.update_achievements()

    def finish(self, target):
        finished = self.copy()
        if finished.lifetime_cookies >= target:
            return finished
        rate = finished.cps()
        if rate <= 0:
            raise ValueError("Cannot reach target with zero CpS")
        duration = (target - finished.lifetime_cookies) / rate
        finished.age += duration
        finished.lifetime_cookies = float(target)
        finished.handmade_cookies += finished.hand_cps() * duration
        finished.update_achievements()
        return finished

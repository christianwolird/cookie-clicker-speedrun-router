from dataclasses import dataclass
from math import ceil, floor

from .data import DEFAULT_VERSION, get_version_data


@dataclass(frozen=True, slots=True)
class Purchase:
    operation: str
    item: str
    age: float
    cookies: float
    tier: int | None = None
    label: str | None = None

    @property
    def display_item(self):
        return self.label or self.item

    def route_action(self):
        if self.operation == "upgrade":
            if self.tier is None:
                raise ValueError(f"Upgrade has no route tier: {self.item}")
            return f"upgrade {self.item} {self.tier}"
        return f"{self.operation} {self.item}"


def purchase_score(parent, child):
    """Pairwise-optimal ordering score for an atomic purchase or chain."""
    cost = child.cookies - parent.cookies
    cps_buff = child.cps() - parent.cps()
    if cost <= 0 or cps_buff <= 0:
        return float("inf")

    # Minimize A * (a + c) / a. This is equivalent to maximizing the original
    # a / (A * (a + c)) score, where A is cost, a is the buff, and c is CpS.
    return cost * child.cps() / cps_buff


class Game:
    """A purchase-point snapshot of a fresh Cookie Clicker ascension.

    ``version`` selects one complete data catalog for the lifetime of the game.
    Each purchase is made as soon as it can be afforded.  ``cookies`` is total
    cookies baked, not the current bank; the model assumes the bank is empty at
    each snapshot.  During ``purchase_delay`` clicking pauses while buildings
    continue producing, matching the simplifying assumption in the original
    prototype.
    """

    def __init__(self, version=DEFAULT_VERSION):
        version_data = get_version_data(version)
        self.version = version_data.VERSION
        self.building_info = version_data.BUILDINGS
        self.upgrade_info = version_data.UPGRADES
        self.achievement_info = version_data.ACHIEVEMENTS
        self.upgrade_families = version_data.UPGRADE_FAMILIES
        self.upgrade_routes = {
            name: (family, tier)
            for family, names in self.upgrade_families.items()
            for tier, name in enumerate(names, 1)
        }

        self.clickrate = 10.0
        self.purchase_delay = 0.5
        self.price_cutoff_multiplier = 2.0
        self.allow_upgrades = True

        self.age = 0.0
        self.cookies = 0.0
        self.handmade_cookies = 0.0
        self.purchase_credit = 0.0

        self.num_buildings = {name: 0 for name in self.building_info}
        self.upgrades = set()
        self.achievements = set()
        self.last_purchase = None
        self._building_cps_cache = None

    def copy(self):
        copy_game = Game(self.version)
        copy_game.clickrate = self.clickrate
        copy_game.purchase_delay = self.purchase_delay
        copy_game.price_cutoff_multiplier = self.price_cutoff_multiplier
        copy_game.allow_upgrades = self.allow_upgrades
        copy_game.age = self.age
        copy_game.cookies = self.cookies
        copy_game.handmade_cookies = self.handmade_cookies
        copy_game.purchase_credit = self.purchase_credit
        copy_game.num_buildings = dict(self.num_buildings)
        copy_game.upgrades = set(self.upgrades)
        copy_game.achievements = set(self.achievements)
        copy_game.last_purchase = self.last_purchase
        copy_game._building_cps_cache = self._building_cps_cache
        return copy_game

    def initialize_neverclick(self):
        """Start immediately after the category's 15 clicks and first Cursor."""
        self.clickrate = 0.0
        self.cookies = 15.0
        self.handmade_cookies = 15.0
        self.num_buildings["Cursor"] = 1
        self._building_cps_cache = None
        self.update_achievements()

    def __str__(self):
        return (
            f"Age: {self.age:.3f} -- Cookies baked: {self.cookies:.0f} "
            f"-- CpS: {self.cps():.3f}"
        )

    def __repr__(self):
        return str(self)

    def price_cutoff(self):
        return max(1_000, self.cookies * self.price_cutoff_multiplier)

    def building_price(self, name):
        base_price = self.building_info[name].base_price
        return ceil(base_price * 1.15 ** self.num_buildings[name])

    def _cursor_bonus(self):
        bonus = sum(
            self.upgrade_info[name].finger_add
            for name in self.upgrades
            if name in self.upgrade_info
        )
        non_cursors = sum(self.num_buildings.values()) - self.num_buildings["Cursor"]
        return bonus * non_cursors

    def _cursor_multiplier(self):
        multiplier = 1.0
        for name in self.upgrades:
            if name in self.upgrade_info:
                multiplier *= self.upgrade_info[name].cursor_multiplier
        return multiplier

    def _building_multiplier(self, name):
        multiplier = 1.0
        for upgrade_name in self.upgrades:
            upgrade = self.upgrade_info[upgrade_name]
            if upgrade.building == name:
                multiplier *= 2
            if upgrade.grandma_synergy:
                if name == "Grandma":
                    multiplier *= 2
                elif name == upgrade.grandma_synergy:
                    building_id = list(self.building_info).index(name)
                    multiplier *= 1 + self.num_buildings["Grandma"] * 0.01 / (building_id - 1)
        return multiplier

    def building_cps(self):
        if self._building_cps_cache is not None:
            return self._building_cps_cache

        total = 0.0
        for name, number in self.num_buildings.items():
            per_building = self.building_info[name].base_cps
            if name == "Cursor":
                per_building = (
                    per_building * self._cursor_multiplier() + self._cursor_bonus()
                )
            total += number * per_building * self._building_multiplier(name)

        for name in self.upgrades:
            total *= self.upgrade_info[name].production_multiplier

        milk = len(self.achievements) / 25
        for name in self.upgrades:
            kitten = self.upgrade_info[name].kitten_coefficient
            if kitten:
                total *= 1 + milk * kitten
        self._building_cps_cache = total
        return self._building_cps_cache

    def cookies_per_click(self):
        power = self._cursor_multiplier() + self._cursor_bonus()
        for name in self.upgrades:
            power += self.upgrade_info[name].mouse_cps_fraction * self.building_cps()
        return power

    def click_cps(self):
        return self.clickrate * self.cookies_per_click()

    def cps(self):
        return self.building_cps() + self.click_cps()

    def _achievement_value(self, achievement):
        if achievement.kind == "cookies":
            return self.cookies
        if achievement.kind == "cps":
            return self.building_cps()
        if achievement.kind == "handmade":
            return self.handmade_cookies
        if achievement.kind == "building":
            return self.num_buildings[achievement.building]
        if achievement.kind == "buildings":
            return sum(self.num_buildings.values())
        if achievement.kind == "upgrades":
            return len(self.upgrades)
        raise ValueError(f"Unknown achievement kind: {achievement.kind}")

    def update_achievements(self):
        # A newly earned achievement can improve a kitten, which can earn the
        # next CpS achievement, so repeat until milk and CpS settle.
        changed = True
        while changed:
            changed = False
            for name, achievement in self.achievement_info.items():
                if name not in self.achievements and (
                    self._achievement_value(achievement) >= achievement.threshold
                ):
                    self.achievements.add(name)
                    if any(
                        self.upgrade_info[item].kitten_coefficient
                        for item in self.upgrades
                    ):
                        self._building_cps_cache = None
                    changed = True

    def _wait_for_purchase(self, price):
        credit = min(price, self.purchase_credit)
        self.purchase_credit -= credit
        price -= credit
        if price == 0:
            return

        rate = self.cps()
        if rate <= 0:
            raise ValueError("Cannot earn cookies with zero CpS")

        click_cps = self.click_cps()
        # Clicking pauses for the purchase delay while buildings keep baking:
        # (auto + hand) * (T - delay) + auto * delay = price.
        # Solving for T gives (price + hand * delay) / total CpS.
        duration = (price + click_cps * self.purchase_delay) / rate
        active_clicking = max(0.0, duration - self.purchase_delay)
        self.handmade_cookies += click_cps * active_clicking
        self.age += duration
        self.cookies += price
        self.update_achievements()

    def purchase_building(self, name):
        price = self.building_price(name)
        self._wait_for_purchase(price)
        self.num_buildings[name] += 1
        self._building_cps_cache = None
        self.last_purchase = Purchase(
            "buy",
            name,
            self.age,
            self.cookies,
            label=f"{name} #{self.num_buildings[name]}",
        )
        self.update_achievements()

    def sell_building(self, name):
        if self.num_buildings[name] <= 0:
            raise ValueError(f"Cannot sell an unowned building: {name}")

        refund = floor(self.building_price(name) / 4)
        self.num_buildings[name] -= 1
        self.purchase_credit += refund
        self._building_cps_cache = None
        self.last_purchase = Purchase(
            "sell",
            name,
            self.age,
            self.cookies,
            label=f"Sell {name} #{self.num_buildings[name] + 1}",
        )
        self.update_achievements()

    def upgrade_unlocked(self, name):
        upgrade = self.upgrade_info[name]
        return (
            all(self.num_buildings[building] >= number for building, number in upgrade.requirements)
            and self.cookies >= upgrade.cookies_required
            and self.handmade_cookies >= upgrade.handmade_required
            and len(self.achievements) >= upgrade.achievements_required
        )

    def purchase_upgrade(self, name):
        if not self.allow_upgrades:
            raise ValueError("Upgrades are disabled")
        if name in self.upgrades:
            raise ValueError(f"Upgrade already purchased: {name}")

        upgrade = self.upgrade_info[name]
        paid = self.copy()
        paid._wait_for_purchase(upgrade.price)
        if not paid.upgrade_unlocked(name):
            raise ValueError(f"Upgrade is still locked: {name}")

        self.age = paid.age
        self.cookies = paid.cookies
        self.handmade_cookies = paid.handmade_cookies
        self.achievements = paid.achievements
        self.upgrades.add(name)
        self._building_cps_cache = None
        route_family, route_tier = self.upgrade_routes.get(name, (name, None))
        self.last_purchase = Purchase(
            "upgrade",
            route_family,
            self.age,
            self.cookies,
            tier=route_tier,
            label=name,
        )
        self.update_achievements()

    def _with_upgrade_prerequisites(self, name, cookie_limit=None):
        """Greedily buy the locally optimal prerequisites, then the upgrade."""
        upgrade = self.upgrade_info[name]
        child = self.copy()
        purchases = []

        while True:
            missing_names = tuple(
                building
                for building, needed in upgrade.requirements
                if child.num_buildings[building] < needed
            )
            if not missing_names:
                break

            options = []
            for building in missing_names:
                option = child.copy()
                option.purchase_building(building)
                if cookie_limit is None or option.cookies < cookie_limit:
                    options.append(option)
            if not options:
                return None
            child = min(options, key=lambda option: purchase_score(child, option))
            purchases.append(child.last_purchase)

        try:
            child.purchase_upgrade(name)
        except ValueError:
            return None
        purchases.append(child.last_purchase)
        return Transition(child, tuple(purchases))

    def children(self, cookie_limit=None):
        cutoff = self.price_cutoff()
        for name in self.num_buildings:
            if self.building_price(name) <= cutoff:
                child = self.copy()
                child.purchase_building(name)
                yield Transition(child, (child.last_purchase,))

        # The cutoff applies to the upgrade itself. Prerequisite buildings are
        # deliberately allowed above it; otherwise locked upgrades can never
        # guide the route tree toward the state that unlocks them.
        if not self.allow_upgrades:
            return
        for name, upgrade in self.upgrade_info.items():
            if name in self.upgrades or upgrade.price > cutoff:
                continue
            transition = self._with_upgrade_prerequisites(name, cookie_limit)
            if transition is not None:
                yield transition

    def finish(self, target):
        finished = self.copy()
        if finished.cookies >= target:
            return finished
        rate = finished.cps()
        if rate <= 0:
            raise ValueError("Cannot reach target with zero CpS")
        duration = (target - finished.cookies) / rate
        finished.age += duration
        finished.cookies = float(target)
        finished.handmade_cookies += finished.click_cps() * duration
        finished.update_achievements()
        return finished


@dataclass(frozen=True, slots=True)
class Transition:
    game: Game
    purchases: tuple[Purchase, ...]

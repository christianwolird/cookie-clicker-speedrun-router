from dataclasses import dataclass
from math import ceil, floor

from .data import DEFAULT_VERSION, get_version_data


DEFAULT_CLICK_RATE = 10.0
DEFAULT_ERRAND_DELAY = 1.0
DEFAULT_ITEM_DELAY = 0.2
DEFAULT_ACTION_DELAY = DEFAULT_ITEM_DELAY


@dataclass(frozen=True, slots=True)
class Purchase:
    operation: str
    item: str
    age: float
    lifetime_cookies: float
    current_cps: float = 0.0
    label: str | None = None
    quantity: int = 1
    required_cookies: float | None = None
    bank_after: float | None = None
    shop_actions: int | None = None

    @property
    def display_item(self):
        return self.label or self.item


class Gamestate:
    """A snapshot of a fresh Cookie Clicker ascension.

    ``version`` selects one complete data catalog for the lifetime of the run.
    ``lifetime_cookies`` is total cookies baked, not the current bank; the
    legacy purchase methods assume an empty bank after purchases. Profiled
    errands use ``game.shop`` to carry unspent cookies and apply fixed bulk
    rules, while retaining simultaneous, grouped production timing.
    """

    def __init__(self, version=DEFAULT_VERSION, achievement_curve=None):
        version_data = get_version_data(version)
        self.version = version_data.VERSION
        self.building_catalog = version_data.BUILDINGS
        self.upgrade_catalog = version_data.UPGRADES
        self.achievement_curve = achievement_curve

        self.click_rate = DEFAULT_CLICK_RATE
        self.errand_delay = DEFAULT_ERRAND_DELAY
        self.action_delay = DEFAULT_ACTION_DELAY
        self.upgrades_allowed = True
        self.bulk_size = 1
        self.selling_allowed = False
        self.legacy_errands = True

        self.age = 0.0
        self.lifetime_cookies = 0.0
        self.handmade_cookies = 0.0
        self.sale_credit = 0.0

        self.building_counts = {name: 0 for name in self.building_catalog}
        self.purchased_upgrades = set()
        self._automatic_cps_cache = None
        self._automatic_cps_cache_achievement_count = None

    def copy(self):
        copied_gamestate = Gamestate(self.version, self.achievement_curve)
        copied_gamestate.click_rate = self.click_rate
        copied_gamestate.errand_delay = self.errand_delay
        copied_gamestate.action_delay = self.action_delay
        copied_gamestate.upgrades_allowed = self.upgrades_allowed
        copied_gamestate.bulk_size = self.bulk_size
        copied_gamestate.selling_allowed = self.selling_allowed
        copied_gamestate.legacy_errands = self.legacy_errands
        copied_gamestate.age = self.age
        copied_gamestate.lifetime_cookies = self.lifetime_cookies
        copied_gamestate.handmade_cookies = self.handmade_cookies
        copied_gamestate.sale_credit = self.sale_credit
        copied_gamestate.building_counts = dict(self.building_counts)
        copied_gamestate.purchased_upgrades = set(self.purchased_upgrades)
        copied_gamestate._automatic_cps_cache = self._automatic_cps_cache
        copied_gamestate._automatic_cps_cache_achievement_count = (
            self._automatic_cps_cache_achievement_count
        )
        return copied_gamestate

    @property
    def item_delay(self):
        """Compatibility alias for legacy per-item timing."""
        return self.action_delay

    @item_delay.setter
    def item_delay(self, value):
        self.action_delay = value

    @property
    def bank(self):
        """Unspent cookies; sale_credit remains a legacy compatibility alias."""
        return self.sale_credit

    @bank.setter
    def bank(self, value):
        self.sale_credit = value

    def building_sale_refund(self, name, quantity=1):
        if quantity < 1 or quantity > self.building_counts[name]:
            raise ValueError(f"Cannot sell {quantity} owned {name}")
        return sum(
            floor(self.building_price(name, -offset) * 0.25 / 1.15)
            for offset in range(quantity)
        )

    def initialize_neverclick(self):
        """Start immediately after the category's 15 clicks and first Cursor."""
        self.click_rate = 0.0
        self.lifetime_cookies = 15.0
        self.handmade_cookies = 15.0
        self.building_counts["Cursor"] = 1
        self._automatic_cps_cache = None
        self._automatic_cps_cache_achievement_count = None

    def __str__(self):
        return (
            f"Age: {self.age:.3f} -- Cookies baked: {self.lifetime_cookies:.0f} "
            f"-- CpS: {self.cps():.3f}"
        )

    def __repr__(self):
        return str(self)

    def building_price(self, name, additional_owned=0):
        base_price = self.building_catalog[name].base_price
        owned = self.building_counts[name] + additional_owned
        return ceil(base_price * 1.15 ** owned)

    def building_group_price(self, name, quantity):
        return sum(
            self.building_price(name, additional_owned=offset)
            for offset in range(quantity)
        )

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

    def achievement_count(self):
        if self.achievement_curve is None:
            return 0
        return self.achievement_curve.count_at(self.lifetime_cookies)

    def automatic_cps(self):
        has_kitten = any(
            self.upgrade_catalog[name].kitten_coefficient
            for name in self.purchased_upgrades
        )
        achievement_count = self.achievement_count() if has_kitten else 0
        if self._automatic_cps_cache is not None and (
            self._automatic_cps_cache_achievement_count == achievement_count
        ):
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

        milk = achievement_count / 25
        for name in self.purchased_upgrades:
            kitten = self.upgrade_catalog[name].kitten_coefficient
            if kitten:
                total *= 1 + milk * kitten
        self._automatic_cps_cache = total
        self._automatic_cps_cache_achievement_count = achievement_count
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

    def errand_pause(self, item_count=1):
        """Return hand-clicking downtime for one errand.

        Every building copy and upgrade contributes one item delay.
        """
        if item_count < 1:
            raise ValueError("item_count must be at least one")
        if self.errand_delay < 0:
            raise ValueError("errand_delay cannot be negative")
        if self.item_delay < 0:
            raise ValueError("item_delay cannot be negative")
        return self.errand_delay + item_count * self.item_delay

    def _advance_to_errand(self, price, item_count=1):
        credit = min(price, self.sale_credit)
        self.sale_credit -= credit
        price -= credit
        if price == 0:
            return

        total_cps = self.cps()
        if total_cps <= 0:
            raise ValueError("Cannot earn cookies with zero CpS")

        hand_cps = self.hand_cps()
        # All purchases close simultaneously with an empty bank. Hand-clicking
        # stops for one trip plus one action per purchased item while the
        # parent's buildings keep baking. Solving
        # (auto + hand) * (T - pause) + auto * pause = price gives
        # T = (price + hand * pause) / total CpS.
        pause = self.errand_pause(item_count)
        duration = (price + hand_cps * pause) / total_cps
        active_clicking = max(0.0, duration - pause)
        self.handmade_cookies += hand_cps * active_clicking
        self.age += duration
        self.lifetime_cookies += price
        self._automatic_cps_cache = None
        self._automatic_cps_cache_achievement_count = None

    def purchase_errand(self, building_quantities=None, upgrades=()):
        """Apply an unordered set of purchases as one zero-bank errand."""
        building_quantities = {
            name: quantity
            for name, quantity in (building_quantities or {}).items()
            if quantity
        }
        upgrades = frozenset(upgrades)

        for name, quantity in building_quantities.items():
            if name not in self.building_catalog:
                raise KeyError(name)
            if not isinstance(quantity, int) or quantity <= 0:
                raise ValueError(
                    f"Building quantity must be a positive integer: {name}"
                )
        if upgrades and not self.upgrades_allowed:
            raise ValueError("Upgrades are disabled")
        for name in upgrades:
            if name not in self.upgrade_catalog:
                raise KeyError(name)
            if name in self.purchased_upgrades:
                raise ValueError(f"Upgrade already purchased: {name}")

        item_count = sum(building_quantities.values()) + len(upgrades)
        if item_count == 0:
            raise ValueError("An errand must contain at least one purchase")

        price = sum(
            self.building_group_price(name, quantity)
            for name, quantity in building_quantities.items()
        ) + sum(self.upgrade_catalog[name].price for name in upgrades)

        completed = self.copy()
        completed._advance_to_errand(price, item_count)
        original_counts = dict(completed.building_counts)
        for name, quantity in building_quantities.items():
            completed.building_counts[name] += quantity
        completed._automatic_cps_cache = None
        completed._automatic_cps_cache_achievement_count = None

        for name in upgrades:
            if not completed.upgrade_unlocked(name):
                raise ValueError(f"Upgrade is still locked: {name}")
        completed.purchased_upgrades.update(upgrades)
        completed._automatic_cps_cache = None
        completed._automatic_cps_cache_achievement_count = None

        purchase_specs = []
        for name, quantity in building_quantities.items():
            for number in range(
                original_counts[name] + 1,
                original_counts[name] + quantity + 1,
            ):
                purchase_specs.append((name, "buy", f"{name} #{number}"))
        purchase_specs.extend(
            (name, "upgrade", None) for name in upgrades
        )
        purchase_specs.sort(key=lambda spec: (spec[0], spec[1]))
        purchases = tuple(
            Purchase(
                operation,
                name,
                completed.age,
                completed.lifetime_cookies,
                current_cps=completed.cps(),
                label=label,
            )
            for name, operation, label in purchase_specs
        )
        self.__dict__.update(completed.__dict__)
        return purchases

    def purchase_building(self, name):
        return self.purchase_errand({name: 1})

    def sell_building(self, name):
        if self.building_counts[name] <= 0:
            raise ValueError(f"Cannot sell an unowned building: {name}")

        # The current buy price is 15% above the price of the last building
        # purchased. Selling returns 25% of that previous purchase price.
        refund = self.building_sale_refund(name)
        self.building_counts[name] -= 1
        self.sale_credit += refund
        self._automatic_cps_cache = None
        self._automatic_cps_cache_achievement_count = None
        purchase = Purchase(
            "sell",
            name,
            self.age,
            self.lifetime_cookies,
            current_cps=self.cps(),
            label=f"Sell {name} #{self.building_counts[name] + 1}",
        )
        return (purchase,)

    def upgrade_unlocked(self, name):
        upgrade = self.upgrade_catalog[name]
        return (
            all(
                self.building_counts[building] >= number
                for building, number in upgrade.requirements
            )
            and self.lifetime_cookies >= upgrade.cookies_required
            and self.handmade_cookies >= upgrade.handmade_required
        )

    def purchase_upgrade(self, name):
        return self.purchase_errand(upgrades=(name,))

    def finish(self, target):
        finished = self.copy()
        if finished.lifetime_cookies >= target:
            return finished
        rate = finished.cps()
        if rate <= 0:
            raise ValueError("Cannot reach target with zero CpS")
        duration = (target - finished.lifetime_cookies) / rate
        if not finished.legacy_errands:
            finished.bank += target - finished.lifetime_cookies
        finished.age += duration
        finished.lifetime_cookies = float(target)
        finished.handmade_cookies += finished.hand_cps() * duration
        finished._automatic_cps_cache = None
        finished._automatic_cps_cache_achievement_count = None
        return finished

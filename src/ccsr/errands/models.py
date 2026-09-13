"""Errand specifications and their evaluated graph neighbors."""

from dataclasses import dataclass
from ..game.actions import RouteAction


@dataclass(frozen=True, slots=True)
class Errand:
    """Count-based x1 errand, or x10 errand with an ordered purchase suffix.

    Sales are always an unordered prefix. Empty sales/order keep legacy x1
    hashing and generation independent of purchase permutations.
    """

    building_quantities: tuple[int, ...]
    upgrades: frozenset[str] = frozenset()
    sales: tuple[int, ...] = ()
    purchase_order: tuple[RouteAction, ...] = ()

    @property
    def item_count(self):
        return sum(self.building_quantities) + sum(self.sales) + len(self.upgrades)

    def action_count(self, bulk_size=1):
        purchases = len(self.purchase_order) if bulk_size == 10 else (
            sum(self.building_quantities) + len(self.upgrades)
        )
        sales = sum((quantity + bulk_size - 1) // bulk_size for quantity in self.sales)
        return purchases + sales + (2 if sales else 0)

    def actions(self, gamestate):
        sales = tuple(
            RouteAction("sell", name, quantity)
            for name, quantity in zip(gamestate.building_catalog, self.sales)
            if quantity
        )
        if gamestate.bulk_size == 10:
            return sales + self.purchase_order
        return sales + tuple(
            RouteAction("buy", name)
            for name, quantity in zip(gamestate.building_catalog, self.building_quantities)
            for _ in range(quantity)
        ) + tuple(RouteAction("upgrade", name) for name in sorted(self.upgrades))


@dataclass(frozen=True, slots=True)
class ErrandNeighbor:
    errand: Errand
    gamestate: object
    purchases: tuple
    score: float
    acquisition_time: float

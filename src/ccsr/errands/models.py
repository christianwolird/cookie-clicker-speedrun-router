"""Errand specifications and their evaluated graph neighbors."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Errand:
    """An unordered set of building quantities and upgrades."""

    building_quantities: tuple[int, ...]
    upgrades: frozenset[str] = frozenset()

    @property
    def item_count(self):
        return sum(self.building_quantities) + len(self.upgrades)


@dataclass(frozen=True, slots=True)
class ErrandNeighbor:
    errand: Errand
    gamestate: object
    purchases: tuple
    score: float
    acquisition_time: float

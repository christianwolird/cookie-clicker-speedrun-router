"""In-memory route models shared by routers, I/O, and replay."""

from dataclasses import dataclass

from ..game.gamestate import DEFAULT_ERRAND_DELAY, DEFAULT_ITEM_DELAY


@dataclass(frozen=True, slots=True)
class RouteAction:
    operation: str
    item: str

    @classmethod
    def from_purchase(cls, purchase):
        return cls(purchase.operation, purchase.item)

    def __str__(self):
        return f"{self.operation} {self.item}"


@dataclass(frozen=True, slots=True)
class RoutePlan:
    name: str
    source: str
    category: str
    player_profile: str
    version: str
    target: int
    click_rate: float
    initial_state: str
    algorithm: str
    upgrades_enabled: bool
    for_quickster: bool
    errands: tuple[tuple[RouteAction, ...], ...]
    errand_delay: float = DEFAULT_ERRAND_DELAY
    item_delay: float = DEFAULT_ITEM_DELAY
    price_horizon_multiplier: float | None = None
    errand_queue_depth: int | None = None
    max_errand_size: int | None = None
    beam_width: int | None = None
    ruler_scale: float | None = None
    ruler_route: str | None = None
    beam_max_expansions: int | None = None

    @property
    def actions(self):
        return tuple(action for errand in self.errands for action in errand)


@dataclass(frozen=True, slots=True)
class RouteResult:
    initial_gamestate: object
    final_gamestate: object
    errands: tuple


def action_errands(result):
    return tuple(
        tuple(RouteAction.from_purchase(purchase) for purchase in errand)
        for errand in result.errands
    )

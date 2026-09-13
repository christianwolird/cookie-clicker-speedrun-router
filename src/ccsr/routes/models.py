"""In-memory route models shared by routers, I/O, and replay."""

from dataclasses import dataclass

from ..game.gamestate import DEFAULT_ERRAND_DELAY, DEFAULT_ACTION_DELAY
from ..game.actions import RouteAction


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
    action_delay: float = DEFAULT_ACTION_DELAY
    price_horizon_multiplier: float | None = None
    errand_queue_depth: int | None = None
    max_errand_size: int | None = None
    beam_width: int | None = None
    ruler_scale: float | None = None
    ruler_route: str | None = None
    beam_max_expansions: int | None = None
    errand_profile: str | None = None
    bulk_size: int = 1
    selling_allowed: bool = True
    errand_search_width: int | None = None
    max_errand_actions: int | None = None
    errand_state_width: int | None = None

    @property
    def item_delay(self):
        """Compatibility alias for reading older plans."""
        return self.action_delay

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

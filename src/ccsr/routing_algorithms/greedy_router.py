"""Greedy routing by repeatedly executing the best locally scored errand."""

from ..errands.generator import (
    DEFAULT_QUEUE_EXPANSIONS,
    DEFAULT_MAX_ERRAND_ACTIONS,
    best_errand,
)
from ..routes.models import RouteResult


def find_route(
    initial_gamestate,
    target,
    on_errand=None,
    price_horizon_multiplier=2.0,
    queue_expansions=DEFAULT_QUEUE_EXPANSIONS,
    for_quickster=False,
    max_errand_actions=DEFAULT_MAX_ERRAND_ACTIONS,
):
    gamestate = initial_gamestate.copy()
    if for_quickster:
        gamestate.errand_delay = 0.0
        gamestate.action_delay = 0.0
    initial = gamestate.copy()
    errands = []
    while gamestate.lifetime_cookies < target:
        neighbor = best_errand(
            gamestate,
            target,
            price_horizon_multiplier,
            queue_expansions,
            singleton_only=for_quickster,
            max_errand_actions=max_errand_actions,
        )
        if neighbor is None:
            break
        errands.append(neighbor.purchases)
        if on_errand is not None:
            on_errand(neighbor.purchases)
        gamestate = neighbor.gamestate
    return RouteResult(initial, gamestate.finish(target), tuple(errands))

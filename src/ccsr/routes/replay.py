"""Route execution against the Cookie Clicker simulator."""

from collections import Counter

from ..config import load_achievement_curve, load_category
from ..game.gamestate import Gamestate
from .models import RouteResult


def initial_gamestate(plan, *, player=None, for_quickster=None, version=None):
    try:
        category = load_category(plan.category)
        curve = load_achievement_curve(category.achievement_curve)
    except ValueError:
        curve = None
    gamestate = Gamestate(version or plan.version, curve)
    if plan.initial_state == "neverclick":
        gamestate.initialize_neverclick()

    effective_quickster = (
        plan.for_quickster if for_quickster is None else for_quickster
    )
    click_rate = plan.click_rate if player is None else player.click_rate
    gamestate.click_rate = 0.0 if plan.initial_state == "neverclick" else click_rate
    gamestate.upgrades_allowed = plan.upgrades_enabled
    if effective_quickster:
        gamestate.errand_delay = 0.0
        gamestate.item_delay = 0.0
    elif player is not None:
        gamestate.errand_delay = player.errand_delay
        gamestate.item_delay = player.item_delay
    else:
        gamestate.errand_delay = plan.errand_delay
        gamestate.item_delay = plan.item_delay
    return gamestate


def apply_errand(gamestate, actions):
    """Apply route actions to a child gamestate and return purchase rows."""
    child = gamestate.copy()
    sales = [action for action in actions if action.operation == "sell"]
    if sales:
        if len(actions) != 1:
            raise ValueError("Sales cannot share an errand with other actions")
        purchases = child.sell_building(sales[0].item)
        return child, purchases

    upgrades = [
        action.item for action in actions if action.operation == "upgrade"
    ]
    if len(upgrades) != len(set(upgrades)):
        raise ValueError("An upgrade cannot occur twice in one errand")
    purchases = child.purchase_errand(
        Counter(
            action.item for action in actions if action.operation == "buy"
        ),
        upgrades,
    )
    return child, purchases


def execute_route(
    plan,
    version=None,
    on_errand=None,
    *,
    player=None,
    for_quickster=None,
):
    """Replay a route until its target is reached."""
    gamestate = initial_gamestate(
        plan,
        player=player,
        for_quickster=for_quickster,
        version=version,
    )
    initial = gamestate.copy()
    completed_errands = []

    for number, actions in enumerate(plan.errands, 1):
        try:
            child, purchases = apply_errand(gamestate, actions)
        except (KeyError, ValueError) as error:
            raise ValueError(f"Errand {number}: {error}") from error
        if actions[0].operation != "sell" and (
            child.lifetime_cookies >= plan.target
        ):
            break
        completed_errands.append(purchases)
        if on_errand is not None:
            on_errand(purchases)
        gamestate = child

    return RouteResult(
        initial,
        gamestate.finish(plan.target),
        tuple(completed_errands),
    )

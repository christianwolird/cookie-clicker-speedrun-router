"""Route execution against the Cookie Clicker simulator."""

from collections import Counter
from dataclasses import replace

from ..config import load_achievement_curve, load_player_profile, load_errand_profile
from ..game.gamestate import Gamestate
from ..game.shop import execute_shop_errand
from .models import RouteResult


def use_route_profile(plan, profile):
    """Apply a named setup while retaining the source action list and timing mode."""
    player = load_player_profile(profile.player_profile)
    errands = load_errand_profile(profile.errand_profile)
    return replace(
        plan, goal=profile.goal, route_profile=profile.name, target=profile.target,
        version=profile.version, player_profile=player.name, click_rate=player.click_rate,
        initial_state=player.initial_state, errand_delay=player.errand_delay,
        action_delay=player.action_delay, errand_profile=errands.name,
        bulk_size=errands.bulk_size, selling_allowed=errands.selling_allowed,
        upgrades_enabled=profile.upgrades_enabled, achievement_curve=profile.achievement_curve,
    )


def initial_gamestate(plan, *, player=None, for_quickster=None, version=None, errand_profile=None):
    curve = load_achievement_curve(plan.achievement_curve)
    gamestate = Gamestate(version or plan.version, curve)
    initial_state = plan.initial_state if player is None else player.initial_state
    if initial_state == "neverclick":
        gamestate.initialize_neverclick()

    effective_quickster = (
        plan.for_quickster if for_quickster is None else for_quickster
    )
    click_rate = plan.click_rate if player is None else player.click_rate
    gamestate.click_rate = 0.0 if initial_state == "neverclick" else click_rate
    gamestate.upgrades_allowed = plan.upgrades_enabled
    gamestate.bulk_size = plan.bulk_size if errand_profile is None else errand_profile.bulk_size
    gamestate.selling_allowed = (
        plan.selling_allowed if errand_profile is None else errand_profile.selling_allowed
    )
    gamestate.legacy_errands = plan.errand_profile is None and errand_profile is None
    if effective_quickster:
        gamestate.errand_delay = 0.0
        gamestate.action_delay = 0.0
    elif player is not None:
        gamestate.errand_delay = player.errand_delay
        gamestate.action_delay = player.action_delay
    else:
        gamestate.errand_delay = plan.errand_delay
        gamestate.action_delay = plan.action_delay
    return gamestate


def apply_errand(gamestate, actions):
    """Apply route actions to a child gamestate and return purchase rows."""
    if not gamestate.legacy_errands:
        return execute_shop_errand(gamestate, actions)
    if any(action.quantity != 1 for action in actions):
        raise ValueError("Bulk actions require an errand profile")
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
    errand_profile=None,
):
    """Replay a route until its target is reached."""
    gamestate = initial_gamestate(
        plan,
        player=player,
        for_quickster=for_quickster,
        version=version,
        errand_profile=errand_profile,
    )
    initial = gamestate.copy()
    completed_errands = []

    for number, actions in enumerate(plan.errands, 1):
        try:
            child, purchases = apply_errand(gamestate, actions)
        except (KeyError, ValueError) as error:
            raise ValueError(f"Errand {number}: {error}") from error
        if (not gamestate.legacy_errands or actions[0].operation != "sell") and (
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

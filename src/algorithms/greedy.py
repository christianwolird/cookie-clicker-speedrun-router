from dataclasses import dataclass

from ..gamestate import Gamestate, Purchase
from .models import RouteResult


@dataclass(frozen=True, slots=True)
class CandidateDescendant:
    gamestate: Gamestate
    purchases: tuple[Purchase, ...]


def upgrade_descendant(ancestor, name, score, lifetime_cookie_limit=None):
    """Build one candidate descendant ending with the named upgrade.

    Missing prerequisites are bought one errand at a time in greedy order. The
    returned gamestate may therefore be several errands removed from ancestor;
    it is not necessarily a child.
    """
    upgrade = ancestor.upgrade_catalog[name]
    descendant = ancestor.copy()
    purchases = []

    while True:
        missing_names = tuple(
            building
            for building, needed in upgrade.requirements
            if descendant.building_counts[building] < needed
        )
        if not missing_names:
            break

        children = []
        for building in missing_names:
            child = descendant.copy()
            child.purchase_building(building)
            if (
                lifetime_cookie_limit is None
                or child.lifetime_cookies < lifetime_cookie_limit
            ):
                children.append(child)
        if not children:
            return None
        descendant = min(
            children,
            key=lambda child: score(descendant, child),
        )
        purchases.append(descendant.last_purchase)

    try:
        descendant.purchase_upgrade(name)
    except ValueError:
        return None
    purchases.append(descendant.last_purchase)
    return CandidateDescendant(descendant, tuple(purchases))


def price_horizon(gamestate, multiplier):
    return max(1_000, gamestate.lifetime_cookies * multiplier)


def candidate_descendants(
    ancestor,
    score,
    price_horizon_multiplier=2.0,
    lifetime_cookie_limit=None,
):
    """Yield strategically chosen descendants of the current gamestate.

    A building candidate is a child because it is one errand away under the
    current approximation. An upgrade candidate can be a more distant
    descendant because its prerequisite purchases each count as errands too.
    """
    horizon = price_horizon(ancestor, price_horizon_multiplier)
    for name in ancestor.building_counts:
        if ancestor.building_price(name) <= horizon:
            child = ancestor.copy()
            child.purchase_building(name)
            yield CandidateDescendant(child, (child.last_purchase,))

    # The horizon applies to the upgrade itself. Prerequisite buildings are
    # deliberately allowed above it; otherwise locked upgrades can never
    # guide the route toward the state that unlocks them.
    if not ancestor.upgrades_allowed:
        return
    for name, upgrade in ancestor.upgrade_catalog.items():
        if name in ancestor.purchased_upgrades or upgrade.price > horizon:
            continue
        descendant = upgrade_descendant(
            ancestor,
            name,
            score,
            lifetime_cookie_limit,
        )
        if descendant is not None:
            yield descendant


def best_descendant(ancestor, target, score, price_horizon_multiplier):
    finish_without_purchase = ancestor.finish(target).age
    candidates = []

    for candidate in candidate_descendants(
        ancestor,
        score,
        price_horizon_multiplier=price_horizon_multiplier,
        lifetime_cookie_limit=target,
    ):
        descendant = candidate.gamestate
        # Reaching the target while saving means the purchase never happens.
        if descendant.lifetime_cookies >= target:
            continue
        # Near the end, do not buy an item that delays the target even if it
        # would be locally first among a longer, no-longer-useful purchase list.
        if descendant.finish(target).age >= finish_without_purchase:
            continue
        candidates.append(candidate)

    return min(
        candidates,
        key=lambda candidate: score(ancestor, candidate.gamestate),
        default=None,
    )


def find_route(
    initial_gamestate,
    score,
    target,
    on_purchase=None,
    price_horizon_multiplier=2.0,
):
    """Greedily recurse on the best-scoring candidate descendant."""
    gamestate = initial_gamestate.copy()
    purchases = []
    while gamestate.lifetime_cookies < target:
        candidate = best_descendant(
            gamestate,
            target,
            score,
            price_horizon_multiplier,
        )
        if candidate is None:
            break
        for purchase in candidate.purchases:
            purchases.append(purchase)
            if on_purchase is not None:
                on_purchase(purchase)
        gamestate = candidate.gamestate
    return RouteResult(gamestate.finish(target), tuple(purchases))

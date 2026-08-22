from dataclasses import dataclass
from heapq import heappop, heappush
from itertools import count

from ..gamestate import Gamestate, Purchase
from ..routes import RouteResult
from .scoring import age_score


DEFAULT_QUEUE_POPS = 100
DEFAULT_FEELERS = 10


@dataclass(frozen=True, slots=True)
class ErrandPlan:
    """An unordered set of building quantities and upgrades."""

    building_quantities: tuple[int, ...]
    upgrades: frozenset[str] = frozenset()

    @property
    def purchase_count(self):
        return sum(self.building_quantities) + len(self.upgrades)


@dataclass(frozen=True, slots=True)
class ErrandCandidate:
    plan: ErrandPlan
    gamestate: Gamestate
    purchases: tuple[Purchase, ...]
    score: float
    effective_cost: float


def _building_quantities(gamestate, plan):
    return {
        name: quantity
        for name, quantity in zip(
            gamestate.building_catalog,
            plan.building_quantities,
        )
        if quantity
    }


def errand_price(gamestate, plan):
    building_price = sum(
        gamestate.building_group_price(name, quantity)
        for name, quantity in _building_quantities(gamestate, plan).items()
    )
    upgrade_price = sum(
        gamestate.upgrade_catalog[name].price for name in plan.upgrades
    )
    return building_price + upgrade_price


def price_horizon(gamestate, multiplier):
    return max(1_000, gamestate.lifetime_cookies * multiplier)


def effective_cost(ancestor, descendant):
    return (descendant.age - ancestor.age) * ancestor.cps()


def _building_plan(gamestate, building):
    quantities = [0] * len(gamestate.building_catalog)
    quantities[list(gamestate.building_catalog).index(building)] = 1
    return ErrandPlan(tuple(quantities))


def _upgrade_plan(gamestate, name):
    quantities = [0] * len(gamestate.building_catalog)
    building_indexes = {
        building: index
        for index, building in enumerate(gamestate.building_catalog)
    }
    for building, required in gamestate.upgrade_catalog[name].requirements:
        quantities[building_indexes[building]] = max(
            0,
            required - gamestate.building_counts[building],
        )
    return ErrandPlan(tuple(quantities), frozenset((name,)))


def initial_errands(gamestate, singleton_only=False):
    for building in gamestate.building_catalog:
        yield _building_plan(gamestate, building)

    if not gamestate.upgrades_allowed:
        return
    for name in gamestate.upgrade_catalog:
        if name in gamestate.purchased_upgrades:
            continue
        plan = _upgrade_plan(gamestate, name)
        if singleton_only and plan.purchase_count != 1:
            continue
        yield plan


def added_purchase_errands(gamestate, plan):
    for index in range(len(plan.building_quantities)):
        quantities = list(plan.building_quantities)
        quantities[index] += 1
        yield ErrandPlan(tuple(quantities), plan.upgrades)

    if not gamestate.upgrades_allowed:
        return
    final_counts = {
        name: gamestate.building_counts[name] + quantity
        for name, quantity in zip(
            gamestate.building_catalog,
            plan.building_quantities,
        )
    }
    for name, upgrade in gamestate.upgrade_catalog.items():
        if name in gamestate.purchased_upgrades or name in plan.upgrades:
            continue
        if all(
            final_counts[building] >= required
            for building, required in upgrade.requirements
        ):
            yield ErrandPlan(
                plan.building_quantities,
                plan.upgrades | {name},
            )


def best_errand(
    ancestor,
    target,
    price_horizon_multiplier=2.0,
    queue_pops=DEFAULT_QUEUE_POPS,
    singleton_only=False,
):
    """Return the best age-scored errand found within a bounded queue search."""
    finish_without_errand = ancestor.finish(target).age
    seen = set()
    serial = count()
    queue = []
    best = None

    def evaluate(plan):
        nonlocal best
        if plan in seen:
            return None
        seen.add(plan)

        price = errand_price(ancestor, plan)
        if price > price_horizon(ancestor, price_horizon_multiplier):
            return None
        # The target is reached while saving, so this errand never occurs. Any
        # larger errand would cost still more and can be ignored as well.
        if ancestor.lifetime_cookies + price >= target:
            return None

        child = ancestor.copy()
        try:
            purchases = child.purchase_errand(
                _building_quantities(ancestor, plan),
                plan.upgrades,
            )
        except (KeyError, ValueError):
            return None

        score = age_score(ancestor, child)
        lower_bound = effective_cost(ancestor, child)
        candidate = ErrandCandidate(
            plan,
            child,
            purchases,
            score,
            lower_bound,
        )
        if child.finish(target).age < finish_without_errand and (
            best is None or score < best.score
        ):
            best = candidate
        return candidate

    seeds = [
        candidate
        for plan in initial_errands(ancestor, singleton_only)
        if (candidate := evaluate(plan)) is not None
    ]
    if singleton_only:
        return best

    for candidate in seeds:
        # An errand's effective cost is a lower bound for the age score of
        # every larger errand made by adding purchases to it.
        if best is None or candidate.effective_cost < best.score:
            heappush(queue, (candidate.score, next(serial), candidate))

    for _ in range(queue_pops):
        if not queue:
            break
        _, _, candidate = heappop(queue)
        if best is not None and candidate.effective_cost >= best.score:
            continue

        for plan in added_purchase_errands(ancestor, candidate.plan):
            added = evaluate(plan)
            if added is None:
                continue
            if best is None or added.effective_cost < best.score:
                heappush(queue, (added.score, next(serial), added))

    return best


def promising_errands(
    ancestor,
    target,
    limit=DEFAULT_FEELERS,
    price_horizon_multiplier=2.0,
    queue_pops=DEFAULT_QUEUE_POPS,
):
    """Return the best age-scored errands found by the bounded queue search.

    Unlike :func:`best_errand`, candidates do not have to improve the time for
    finishing immediately after that errand. Inventory search deliberately
    needs locally weak edges that may lead to stronger later purchases.
    """
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    if queue_pops <= 0:
        raise ValueError("queue_pops must be greater than zero")

    seen = set()
    serial = count()
    queue = []
    candidates = []

    def evaluate(plan):
        if plan in seen:
            return None
        seen.add(plan)

        price = errand_price(ancestor, plan)
        if price > price_horizon(ancestor, price_horizon_multiplier):
            return None
        if ancestor.lifetime_cookies + price >= target:
            return None

        child = ancestor.copy()
        try:
            purchases = child.purchase_errand(
                _building_quantities(ancestor, plan),
                plan.upgrades,
            )
        except (KeyError, ValueError):
            return None

        candidate = ErrandCandidate(
            plan,
            child,
            purchases,
            age_score(ancestor, child),
            effective_cost(ancestor, child),
        )
        candidates.append(candidate)
        return candidate

    seeds = [
        candidate
        for plan in initial_errands(ancestor)
        if (candidate := evaluate(plan)) is not None
    ]
    for candidate in seeds:
        heappush(queue, (candidate.score, next(serial), candidate))

    for _ in range(queue_pops):
        if not queue:
            break
        _, _, candidate = heappop(queue)
        for plan in added_purchase_errands(ancestor, candidate.plan):
            added = evaluate(plan)
            if added is not None:
                heappush(queue, (added.score, next(serial), added))

    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.score,
                candidate.plan.purchase_count,
            ),
        )[:limit]
    )


def find_route(
    initial_gamestate,
    target,
    on_errand=None,
    price_horizon_multiplier=2.0,
    queue_pops=DEFAULT_QUEUE_POPS,
    singleton_only=False,
):
    gamestate = initial_gamestate.copy()
    errands = []
    while gamestate.lifetime_cookies < target:
        candidate = best_errand(
            gamestate,
            target,
            price_horizon_multiplier,
            queue_pops,
            singleton_only,
        )
        if candidate is None:
            break
        errands.append(candidate.purchases)
        if on_errand is not None:
            on_errand(candidate.purchases)
        gamestate = candidate.gamestate
    return RouteResult(gamestate.finish(target), tuple(errands))


def find_singleton_route(
    initial_gamestate,
    target,
    on_errand=None,
    price_horizon_multiplier=2.0,
):
    return find_route(
        initial_gamestate,
        target,
        on_errand=on_errand,
        price_horizon_multiplier=price_horizon_multiplier,
        singleton_only=True,
    )

"""Generate and score candidate errands from one gamestate."""

from heapq import heapify, heappop, heappush
from itertools import count

from .models import Errand, ErrandNeighbor
from .scoring import age_score


DEFAULT_QUEUE_EXPANSIONS = 100
DEFAULT_BEAM_WIDTH = 10


def _building_quantities(gamestate, errand):
    return {
        name: quantity
        for name, quantity in zip(
            gamestate.building_catalog,
            errand.building_quantities,
        )
        if quantity
    }


def errand_price(gamestate, errand):
    building_price = sum(
        gamestate.building_group_price(name, quantity)
        for name, quantity in _building_quantities(gamestate, errand).items()
    )
    upgrade_price = sum(
        gamestate.upgrade_catalog[name].price for name in errand.upgrades
    )
    return building_price + upgrade_price


def price_horizon(gamestate, multiplier):
    return max(1_000, gamestate.lifetime_cookies * multiplier)


def acquisition_time(ancestor, descendant):
    return descendant.age - ancestor.age


def _building_errand(gamestate, building):
    quantities = [0] * len(gamestate.building_catalog)
    quantities[list(gamestate.building_catalog).index(building)] = 1
    return Errand(tuple(quantities))


def _upgrade_errand(gamestate, name):
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
    return Errand(tuple(quantities), frozenset((name,)))


def initial_errands(gamestate, singleton_only=False):
    for building in gamestate.building_catalog:
        yield _building_errand(gamestate, building)

    if not gamestate.upgrades_allowed:
        return
    for name in gamestate.upgrade_catalog:
        if name in gamestate.purchased_upgrades:
            continue
        errand = _upgrade_errand(gamestate, name)
        if singleton_only and errand.item_count != 1:
            continue
        yield errand


def added_purchase_errands(gamestate, errand):
    for index in range(len(errand.building_quantities)):
        quantities = list(errand.building_quantities)
        quantities[index] += 1
        yield Errand(tuple(quantities), errand.upgrades)

    if not gamestate.upgrades_allowed:
        return
    final_counts = {
        name: gamestate.building_counts[name] + quantity
        for name, quantity in zip(
            gamestate.building_catalog,
            errand.building_quantities,
        )
    }
    for name, upgrade in gamestate.upgrade_catalog.items():
        if name in gamestate.purchased_upgrades or name in errand.upgrades:
            continue
        if all(
            final_counts[building] >= required
            for building, required in upgrade.requirements
        ):
            yield Errand(
                errand.building_quantities,
                errand.upgrades | {name},
            )


def _evaluate(ancestor, target, errand, price_horizon_multiplier):
    price = errand_price(ancestor, errand)
    if price > price_horizon(ancestor, price_horizon_multiplier):
        return None
    if ancestor.lifetime_cookies + price >= target:
        return None

    child = ancestor.copy()
    try:
        purchases = child.purchase_errand(
            _building_quantities(ancestor, errand),
            errand.upgrades,
        )
    except (KeyError, ValueError):
        return None
    return ErrandNeighbor(
        errand,
        child,
        purchases,
        age_score(ancestor, child),
        acquisition_time(ancestor, child),
    )


def best_errand(
    ancestor,
    target,
    price_horizon_multiplier=2.0,
    queue_expansions=DEFAULT_QUEUE_EXPANSIONS,
    singleton_only=False,
):
    """Return the best age-scored errand found within the search budget."""
    finish_without_errand = ancestor.finish(target).age
    seen = set()
    serial = count()
    queue = []
    best = None

    def evaluate(errand):
        nonlocal best
        if errand in seen:
            return None
        seen.add(errand)
        neighbor = _evaluate(
            ancestor,
            target,
            errand,
            price_horizon_multiplier,
        )
        if neighbor is None:
            return None
        if neighbor.gamestate.finish(target).age < finish_without_errand and (
            best is None or neighbor.score < best.score
        ):
            best = neighbor
        return neighbor

    seeds = [
        neighbor
        for errand in initial_errands(ancestor, singleton_only)
        if (neighbor := evaluate(errand)) is not None
    ]
    if singleton_only:
        return best

    for neighbor in seeds:
        if best is None or neighbor.acquisition_time < best.score:
            heappush(queue, (neighbor.score, next(serial), neighbor))

    for _ in range(queue_expansions):
        if not queue:
            break
        _, _, neighbor = heappop(queue)
        if best is not None and neighbor.acquisition_time >= best.score:
            continue
        for errand in added_purchase_errands(ancestor, neighbor.errand):
            added = evaluate(errand)
            if added is not None and (
                best is None or added.acquisition_time < best.score
            ):
                heappush(queue, (added.score, next(serial), added))
    return best


def generate_neighbors(
    ancestor,
    target,
    width=DEFAULT_BEAM_WIDTH,
    price_horizon_multiplier=2.0,
    singleton_only=False,
):
    """Return up to ``width`` promising outgoing errand neighbors.

    Quickster mode evaluates the complete singleton candidate set, then returns
    its best ``width`` members. Human-delay mode uses a bounded inner beam whose
    queue and result roster both have size ``width``.
    """
    if width <= 0:
        raise ValueError("width must be greater than zero")

    def order(neighbor):
        return neighbor.score, neighbor.errand.item_count

    if singleton_only:
        neighbors = (
            neighbor
            for errand in initial_errands(ancestor, singleton_only=True)
            if (
                neighbor := _evaluate(
                    ancestor,
                    target,
                    errand,
                    price_horizon_multiplier,
                )
            )
            is not None
        )
        return tuple(sorted(neighbors, key=order)[:width])

    seen = set()
    serial = count()
    queue = []
    roster = []

    def evaluate(errand):
        if errand in seen:
            return None
        seen.add(errand)
        return _evaluate(
            ancestor,
            target,
            errand,
            price_horizon_multiplier,
        )

    def push_bounded(neighbor):
        entry = (*order(neighbor), next(serial), neighbor)
        if len(queue) < width:
            heappush(queue, entry)
            return
        worst_index = max(range(len(queue)), key=lambda index: queue[index][:3])
        if entry[:2] >= queue[worst_index][:2]:
            return
        queue[worst_index] = entry
        heapify(queue)

    for errand in initial_errands(ancestor):
        neighbor = evaluate(errand)
        if neighbor is not None:
            push_bounded(neighbor)

    while queue:
        if len(roster) == width and queue[0][0] > roster[-1].score:
            break
        _, _, _, neighbor = heappop(queue)
        roster.append(neighbor)
        roster.sort(key=order)
        if len(roster) > width:
            roster.pop()
        for errand in added_purchase_errands(ancestor, neighbor.errand):
            child = evaluate(errand)
            if child is not None:
                push_bounded(child)
    return tuple(roster)

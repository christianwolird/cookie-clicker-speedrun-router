"""Generate and score candidate errands from one gamestate."""

from heapq import heapify, heappop, heappush
from itertools import count
from dataclasses import replace
from math import isfinite

from .models import Errand, ErrandNeighbor
from .scoring import age_score
from ..game.actions import RouteAction
from ..game.shop import execute_shop_errand, sticker_price


DEFAULT_QUEUE_EXPANSIONS = 100
DEFAULT_BEAM_WIDTH = 10
DEFAULT_MAX_ERRAND_ACTIONS = 100


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
    if errand.sales or gamestate.bulk_size == 10:
        return sticker_price(gamestate, errand.actions(gamestate))
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


def _building_errand(gamestate, building, quantity=1):
    quantities = [0] * len(gamestate.building_catalog)
    quantities[list(gamestate.building_catalog).index(building)] = quantity
    order = (RouteAction("buy", building, quantity),) if gamestate.bulk_size == 10 else ()
    return Errand(tuple(quantities), purchase_order=order)


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
    order = ()
    if gamestate.bulk_size == 10:
        # Full batches leave enough bank for the prerequisite upgrade.
        quantities = [((quantity + 9) // 10) * 10 for quantity in quantities]
        order = tuple(
            RouteAction("buy", building, 10)
            for building, quantity in zip(gamestate.building_catalog, quantities)
            for _ in range(quantity // 10)
        ) + (RouteAction("upgrade", name),)
    return Errand(tuple(quantities), frozenset((name,)), purchase_order=order)


def initial_errands(gamestate, singleton_only=False):
    for building in gamestate.building_catalog:
        for quantity in range(1, gamestate.bulk_size + 1):
            yield _building_errand(gamestate, building, quantity)

    if gamestate.selling_allowed:
        for index, owned in enumerate(gamestate.building_counts.values()):
            if owned:
                sales = [0] * len(gamestate.building_catalog)
                sales[index] = min(gamestate.bulk_size, owned)
                yield Errand((0,) * len(sales), sales=tuple(sales))

    if not gamestate.upgrades_allowed:
        return
    for name in gamestate.upgrade_catalog:
        if name in gamestate.purchased_upgrades:
            continue
        errand = _upgrade_errand(gamestate, name)
        if singleton_only and errand.action_count(gamestate.bulk_size) != 1:
            continue
        yield errand


def added_purchase_errands(gamestate, errand):
    sales = errand.sales or (0,) * len(errand.building_quantities)
    partial_buildings = set()
    if gamestate.bulk_size == 10 and not any(sales) and not any(
        action.operation == "sell" for action in errand.purchase_order
    ):
        # With no sales, a later partial buy of the same building would have
        # been affordable during its first partial buy, forcing an overbuy.
        partial_buildings = {
            action.item for action in errand.purchase_order
            if action.operation == "buy" and action.quantity < 10
        }
    for index, name in enumerate(gamestate.building_catalog):
        # Buying back a building in the same grouped errand adds no production.
        if sales[index]:
            continue
        first_quantity = gamestate.bulk_size if name in partial_buildings else 1
        for quantity in range(first_quantity, gamestate.bulk_size + 1):
            quantities = list(errand.building_quantities)
            quantities[index] += quantity
            order = errand.purchase_order
            if gamestate.bulk_size == 10:
                order += (RouteAction("buy", name, quantity),)
            yield replace(errand, building_quantities=tuple(quantities), purchase_order=order)

    if gamestate.selling_allowed:
        for index, owned in enumerate(gamestate.building_counts.values()):
            remaining = owned - sales[index]
            if remaining and not errand.building_quantities[index]:
                child_sales = list(sales)
                child_sales[index] += min(gamestate.bulk_size, remaining)
                yield replace(errand, sales=tuple(child_sales))

    if not gamestate.upgrades_allowed:
        return
    final_counts = {
        name: gamestate.building_counts[name] + quantity - sold
        for name, quantity, sold in zip(
            gamestate.building_catalog,
            errand.building_quantities,
            sales,
        )
    }
    for name, upgrade in gamestate.upgrade_catalog.items():
        if name in gamestate.purchased_upgrades or name in errand.upgrades:
            continue
        if all(
            final_counts[building] >= required
            for building, required in upgrade.requirements
        ):
            yield replace(
                errand,
                upgrades=errand.upgrades | {name},
                purchase_order=(
                    errand.purchase_order + (RouteAction("upgrade", name),)
                    if gamestate.bulk_size == 10 else ()
                ),
            )


def _evaluate(ancestor, target, errand, price_horizon_multiplier):
    price = errand_price(ancestor, errand)
    if price > price_horizon(ancestor, price_horizon_multiplier):
        return None
    if ancestor.lifetime_cookies + max(0, price - ancestor.bank) >= target:
        return None

    child = ancestor.copy()
    try:
        if ancestor.legacy_errands and not errand.sales and ancestor.bulk_size == 1:
            purchases = child.purchase_errand(
                _building_quantities(ancestor, errand), errand.upgrades,
            )
        else:
            child, purchases = execute_shop_errand(ancestor, errand.actions(ancestor))
    except (KeyError, ValueError):
        return None
    if child.lifetime_cookies >= target:
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
    max_errand_actions=DEFAULT_MAX_ERRAND_ACTIONS,
):
    """Return the best age-scored errand found within the search budget."""
    if queue_expansions <= 0 or max_errand_actions <= 0:
        raise ValueError("Errand search limits must be greater than zero")
    finish_without_errand = ancestor.finish(target).age
    seen = set()
    serial = count()
    queue = []
    best = None

    def evaluate(errand):
        nonlocal best
        if errand.action_count(ancestor.bulk_size) > max_errand_actions:
            return None
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
        if neighbor.gamestate.cps() > 0 and isfinite(neighbor.score) and (
            neighbor.gamestate.finish(target).age < finish_without_errand
        ) and (
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
        if ancestor.selling_allowed or best is None or neighbor.acquisition_time < best.score:
            heappush(queue, (neighbor.score, next(serial), neighbor))

    for _ in range(queue_expansions):
        if not queue:
            break
        _, _, neighbor = heappop(queue)
        if not ancestor.selling_allowed and best is not None and neighbor.acquisition_time >= best.score:
            continue
        for errand in added_purchase_errands(ancestor, neighbor.errand):
            added = evaluate(errand)
            if added is not None and (
                ancestor.selling_allowed or best is None or added.acquisition_time < best.score
            ):
                heappush(queue, (added.score, next(serial), added))
    return best


def generate_neighbors(
    ancestor,
    target,
    width=DEFAULT_BEAM_WIDTH,
    price_horizon_multiplier=2.0,
    singleton_only=False,
    search_width=None,
    queue_expansions=DEFAULT_QUEUE_EXPANSIONS,
    max_errand_actions=DEFAULT_MAX_ERRAND_ACTIONS,
):
    """Return up to ``width`` promising outgoing errand neighbors.

    Quickster mode evaluates the complete singleton candidate set, then returns
    its best ``width`` members. Human-delay mode uses a bounded inner queue of
    ``search_width`` candidates and a result roster of ``width`` neighbors.
    Count-based x1 errands never enumerate purchase permutations.
    """
    if width <= 0:
        raise ValueError("width must be greater than zero")
    search_width = width if search_width is None else search_width
    if search_width <= 0 or queue_expansions <= 0 or max_errand_actions <= 0:
        raise ValueError("Errand search limits must be greater than zero")

    def order(neighbor):
        return neighbor.score, neighbor.errand.action_count(ancestor.bulk_size)

    if singleton_only:
        neighbors = (
            neighbor
            for errand in initial_errands(ancestor, singleton_only=True)
            if errand.action_count(ancestor.bulk_size) <= max_errand_actions
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
        if errand.action_count(ancestor.bulk_size) > max_errand_actions:
            return None
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
        if len(queue) < search_width:
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

    for _ in range(queue_expansions):
        if not queue:
            break
        if not ancestor.selling_allowed and len(roster) == width and queue[0][0] > roster[-1].score:
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

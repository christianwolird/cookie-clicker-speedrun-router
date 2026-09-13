"""Beam search over inventory states using a route-based Ruler heuristic."""

from dataclasses import dataclass
from heapq import heappop, heappush, nsmallest
from itertools import count
from time import monotonic

from ..errands.generator import (
    DEFAULT_BEAM_WIDTH, DEFAULT_QUEUE_EXPANSIONS, DEFAULT_MAX_ERRAND_ACTIONS,
    generate_neighbors,
)
from .greedy_router import find_route as find_greedy_route
from .route_ruler import DEFAULT_RULER_SCALE, RouteRuler


DEFAULT_MAX_EXPANSIONS = 10_000
DEFAULT_PROGRESS_INTERVAL = 30.0
PROGRESS_FRONTIER_SIZE = 3


@dataclass(frozen=True, slots=True)
class FrontierCandidate:
    estimated_finish: float
    age: float
    lifetime_cookies: float
    cps: float
    incoming_errand: tuple


@dataclass(frozen=True, slots=True)
class BeamSearchProgress:
    elapsed_seconds: float
    expanded: int
    generated: int
    relaxed: int
    stale_skipped: int
    queue_size: int
    maximum_queue_size: int
    best_finish_age: float
    frontier: tuple[FrontierCandidate, ...]


@dataclass(frozen=True, slots=True)
class BeamSearchStats:
    elapsed_seconds: float
    expanded: int
    generated: int
    relaxed: int
    stale_skipped: int
    heuristic_evaluations: int
    maximum_queue_size: int
    ruler_generated: bool
    ruler_route_age: float
    termination: str


@dataclass(frozen=True, slots=True)
class BeamSearchResult:
    initial_gamestate: object
    final_gamestate: object
    errands: tuple
    search_stats: BeamSearchStats
    ruler_route: object


def inventory_key(gamestate):
    key = (
        tuple(gamestate.building_counts.values()),
        frozenset(gamestate.purchased_upgrades),
    )
    if gamestate.legacy_errands and not gamestate.selling_allowed:
        return key
    # Equal inventories reached via sales can differ in baked cookies, bank,
    # and unlock progress. Never merge these solely on arrival age.
    return key + (
        gamestate.bank, gamestate.lifetime_cookies, gamestate.handmade_cookies,
        gamestate.bulk_size, gamestate.selling_allowed,
    )


def _reconstruct_errands(goal_source, came_from):
    errands = []
    current = goal_source
    while current in came_from:
        current, errand = came_from[current]
        errands.append(errand)
    errands.reverse()
    return tuple(errands)


def _frontier_candidates(queue, best_state_by_inventory, came_from):
    live_entries = (
        entry
        for entry in queue
        if best_state_by_inventory.get(inventory_key(entry[2])) is entry[2]
    )
    frontier = []
    for estimated_finish, _, gamestate in nsmallest(
        PROGRESS_FRONTIER_SIZE,
        live_entries,
    ):
        incoming = came_from.get(gamestate)
        frontier.append(
            FrontierCandidate(
                estimated_finish=estimated_finish,
                age=gamestate.age,
                lifetime_cookies=gamestate.lifetime_cookies,
                cps=gamestate.cps(),
                incoming_errand=incoming[1] if incoming is not None else (),
            )
        )
    return tuple(frontier)


def find_route(
    initial_gamestate,
    target,
    on_errand=None,
    price_horizon_multiplier=2.0,
    beam_width=DEFAULT_BEAM_WIDTH,
    ruler_route=None,
    ruler_scale=DEFAULT_RULER_SCALE,
    max_expansions=DEFAULT_MAX_EXPANSIONS,
    on_progress=None,
    progress_interval=DEFAULT_PROGRESS_INTERVAL,
    for_quickster=False,
    errand_search_width=None,
    errand_queue_expansions=DEFAULT_QUEUE_EXPANSIONS,
    max_errand_actions=DEFAULT_MAX_ERRAND_ACTIONS,
):
    """Search inventories with a supplied or temporary greedy Ruler route."""
    if beam_width <= 0:
        raise ValueError("beam_width must be greater than zero")
    if (errand_search_width is not None and errand_search_width <= 0) or (
        errand_queue_expansions <= 0 or max_errand_actions <= 0
    ):
        raise ValueError("Errand search limits must be greater than zero")
    if ruler_scale < 0:
        raise ValueError("ruler_scale cannot be negative")
    if max_expansions is not None and max_expansions <= 0:
        raise ValueError("max_expansions must be greater than zero")
    if progress_interval <= 0:
        raise ValueError("progress_interval must be greater than zero")

    started_at = monotonic()
    next_progress = started_at + progress_interval
    initial = initial_gamestate.copy()
    if for_quickster:
        initial.errand_delay = 0.0
        initial.action_delay = 0.0

    ruler_generated = ruler_route is None
    if ruler_generated:
        ruler_route = find_greedy_route(
            initial,
            target,
            price_horizon_multiplier=price_horizon_multiplier,
            for_quickster=for_quickster,
            queue_expansions=errand_queue_expansions,
            max_errand_actions=max_errand_actions,
        )
    if ruler_route.final_gamestate.lifetime_cookies < target:
        raise ValueError("Ruler route does not reach the search target")
    if ruler_route.initial_gamestate.version != initial.version:
        raise ValueError("Ruler route uses a different game version")
    ruler_initial = ruler_route.initial_gamestate
    if (ruler_initial.bulk_size, ruler_initial.selling_allowed, ruler_initial.legacy_errands) != (
        initial.bulk_size, initial.selling_allowed, initial.legacy_errands
    ):
        raise ValueError("Ruler route uses different errand rules")
    initial_fields = (
        "age", "lifetime_cookies", "handmade_cookies", "bank", "building_counts",
        "purchased_upgrades", "click_rate", "errand_delay", "action_delay",
        "upgrades_allowed", "achievement_curve",
    )
    if any(getattr(ruler_initial, field) != getattr(initial, field) for field in initial_fields):
        raise ValueError("Ruler route must use the same initial state and player timing")
    if ruler_route.final_gamestate.lifetime_cookies != target:
        raise ValueError("Ruler route must finish at the search target")
    ruler = RouteRuler(ruler_route, ruler_scale)

    best_state_by_inventory = {inventory_key(initial): initial}
    came_from = {}
    serial = count()
    queue = []
    expanded = generated = relaxed = stale_skipped = 0
    heuristic_evaluations = 0
    maximum_queue_size = 0

    def priority(gamestate):
        nonlocal heuristic_evaluations
        heuristic_evaluations += 1
        return gamestate.age + ruler(gamestate)

    heappush(queue, (priority(initial), next(serial), initial))
    maximum_queue_size = 1
    best_goal_source = initial
    best_finish = initial.finish(target)
    if ruler_route.final_gamestate.age < best_finish.age:
        best_goal_source = None
        best_finish = ruler_route.final_gamestate
    termination = "queue_exhausted"

    while queue:
        now = monotonic()
        if on_progress is not None and now >= next_progress:
            on_progress(
                BeamSearchProgress(
                    elapsed_seconds=now - started_at,
                    expanded=expanded,
                    generated=generated,
                    relaxed=relaxed,
                    stale_skipped=stale_skipped,
                    queue_size=len(queue),
                    maximum_queue_size=maximum_queue_size,
                    best_finish_age=best_finish.age,
                    frontier=_frontier_candidates(
                        queue,
                        best_state_by_inventory,
                        came_from,
                    ),
                )
            )
            next_progress = now + progress_interval

        estimated_finish, _, gamestate = heappop(queue)
        key = inventory_key(gamestate)
        if best_state_by_inventory.get(key) is not gamestate:
            stale_skipped += 1
            continue
        if estimated_finish >= best_finish.age:
            termination = "heuristic_bound"
            break
        if max_expansions is not None and expanded >= max_expansions:
            termination = "expansion_limit"
            break

        expanded += 1
        neighbors = generate_neighbors(
            gamestate,
            target,
            width=beam_width,
            price_horizon_multiplier=price_horizon_multiplier,
            singleton_only=for_quickster,
            search_width=errand_search_width,
            queue_expansions=errand_queue_expansions,
            max_errand_actions=max_errand_actions,
        )
        generated += len(neighbors)

        for neighbor in neighbors:
            child = neighbor.gamestate
            if child.cps() <= 0:
                continue
            child_key = inventory_key(child)
            previous = best_state_by_inventory.get(child_key)
            if previous is not None and previous.age <= child.age:
                continue

            best_state_by_inventory[child_key] = child
            came_from[child] = (gamestate, neighbor.purchases)
            relaxed += 1
            finished = child.finish(target)
            if finished.age < best_finish.age:
                best_finish = finished
                best_goal_source = child
            heappush(queue, (priority(child), next(serial), child))
            maximum_queue_size = max(maximum_queue_size, len(queue))

    errands = (
        ruler_route.errands if best_goal_source is None
        else _reconstruct_errands(best_goal_source, came_from)
    )
    if on_errand is not None:
        for errand in errands:
            on_errand(errand)

    stats = BeamSearchStats(
        elapsed_seconds=monotonic() - started_at,
        expanded=expanded,
        generated=generated,
        relaxed=relaxed,
        stale_skipped=stale_skipped,
        heuristic_evaluations=heuristic_evaluations,
        maximum_queue_size=maximum_queue_size,
        ruler_generated=ruler_generated,
        ruler_route_age=ruler_route.final_gamestate.age,
        termination=termination,
    )
    return BeamSearchResult(initial, best_finish, errands, stats, ruler_route)

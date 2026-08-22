"""Best-first inventory search using fuzzy zero-delay completion routes."""

from dataclasses import dataclass
from heapq import heappop, heappush, nsmallest
from itertools import count
from time import monotonic

from .errand_queueing import (
    DEFAULT_FEELERS,
    DEFAULT_QUEUE_POPS,
    find_singleton_route,
    promising_errands,
)


DEFAULT_FUZZY_SCALE = 1.0
DEFAULT_MAX_EXPANSIONS = 10_000
DEFAULT_CHECKPOINT_BASE = 100
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
class InventorySearchProgress:
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
class InventorySearchStats:
    elapsed_seconds: float
    expanded: int
    generated: int
    relaxed: int
    stale_skipped: int
    heuristic_evaluations: int
    fuzzy_route_evaluations: int
    checkpoint_tails: int
    maximum_queue_size: int
    termination: str


@dataclass(frozen=True, slots=True)
class InventorySearchResult:
    final_gamestate: object
    errands: tuple
    search_stats: InventorySearchStats


def inventory_key(gamestate):
    """Return the buildings-and-upgrades identity used for state merging."""
    return (
        tuple(gamestate.building_counts.values()),
        frozenset(gamestate.purchased_upgrades),
    )


def fuzzy_remaining_time(gamestate, target, price_horizon_multiplier=2.0):
    """Estimate remaining time with greedy singleton, zero-delay purchases."""
    if gamestate.lifetime_cookies >= target:
        return 0.0
    fuzzy = gamestate.copy()
    fuzzy.errand_duration = 0.0
    fuzzy.purchase_click_rate = float("inf")
    result = find_singleton_route(
        fuzzy,
        target,
        price_horizon_multiplier=price_horizon_multiplier,
    )
    return max(0.0, result.final_gamestate.age - gamestate.age)


class SharedFuzzyHeuristic:
    """Fuzzy completion estimates with shared geometric checkpoint tails."""

    def __init__(
        self,
        initial_gamestate,
        target,
        price_horizon_multiplier=2.0,
        checkpoint_base=DEFAULT_CHECKPOINT_BASE,
    ):
        self.initial_gamestate = initial_gamestate.copy()
        self.target = target
        self.price_horizon_multiplier = price_horizon_multiplier
        self.checkpoints = self._checkpoints(checkpoint_base)
        self.reference_states = {}
        self.shared_tails = {}
        self.route_evaluations = 0

    def _checkpoints(self, checkpoint_base):
        checkpoints = []
        checkpoint = checkpoint_base
        while checkpoint <= self.initial_gamestate.lifetime_cookies:
            checkpoint *= 10
        while checkpoint < self.target:
            checkpoints.append(checkpoint)
            checkpoint *= 10
        return tuple(checkpoints)

    def _fuzzy_result(self, gamestate, target):
        self.route_evaluations += 1
        fuzzy = gamestate.copy()
        fuzzy.errand_duration = 0.0
        fuzzy.purchase_click_rate = float("inf")
        return find_singleton_route(
            fuzzy,
            target,
            price_horizon_multiplier=self.price_horizon_multiplier,
        )

    def _reference_state(self, checkpoint):
        if checkpoint not in self.reference_states:
            result = self._fuzzy_result(self.initial_gamestate, checkpoint)
            self.reference_states[checkpoint] = result.final_gamestate
        return self.reference_states[checkpoint]

    def _shared_tail(self, checkpoint):
        if checkpoint not in self.shared_tails:
            reference = self._reference_state(checkpoint)
            result = self._fuzzy_result(reference, self.target)
            self.shared_tails[checkpoint] = (
                result.final_gamestate.age - reference.age
            )
        return self.shared_tails[checkpoint]

    def __call__(self, gamestate):
        if gamestate.lifetime_cookies >= self.target:
            return 0.0
        checkpoint = next(
            (
                checkpoint
                for checkpoint in self.checkpoints
                if gamestate.lifetime_cookies < checkpoint
            ),
            None,
        )
        if checkpoint is None:
            result = self._fuzzy_result(gamestate, self.target)
            return result.final_gamestate.age - gamestate.age

        result = self._fuzzy_result(gamestate, checkpoint)
        if (
            checkpoint not in self.reference_states
            and gamestate.age == self.initial_gamestate.age
            and gamestate.lifetime_cookies
            == self.initial_gamestate.lifetime_cookies
            and inventory_key(gamestate)
            == inventory_key(self.initial_gamestate)
        ):
            self.reference_states[checkpoint] = result.final_gamestate
        checkpoint_duration = result.final_gamestate.age - gamestate.age
        return checkpoint_duration + self._shared_tail(checkpoint)


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
    queue_pops=DEFAULT_QUEUE_POPS,
    feelers=DEFAULT_FEELERS,
    fuzzy_scale=DEFAULT_FUZZY_SCALE,
    max_expansions=DEFAULT_MAX_EXPANSIONS,
    on_progress=None,
    progress_interval=DEFAULT_PROGRESS_INTERVAL,
):
    """Search inventories, retaining only the youngest state per inventory."""
    if feelers <= 0:
        raise ValueError("feelers must be greater than zero")
    if fuzzy_scale < 0:
        raise ValueError("fuzzy_scale cannot be negative")
    if max_expansions is not None and max_expansions <= 0:
        raise ValueError("max_expansions must be greater than zero")
    if progress_interval <= 0:
        raise ValueError("progress_interval must be greater than zero")

    started_at = monotonic()
    next_progress = started_at + progress_interval
    initial = initial_gamestate.copy()
    best_state_by_inventory = {inventory_key(initial): initial}
    came_from = {}
    serial = count()
    queue = []

    expanded = 0
    generated = 0
    relaxed = 0
    stale_skipped = 0
    heuristic_evaluations = 0
    maximum_queue_size = 0
    heuristic = SharedFuzzyHeuristic(
        initial,
        target,
        price_horizon_multiplier,
    )

    def priority(gamestate):
        nonlocal heuristic_evaluations
        heuristic_evaluations += 1
        remaining = heuristic(gamestate)
        return gamestate.age + fuzzy_scale * remaining

    heappush(queue, (priority(initial), next(serial), initial))
    maximum_queue_size = 1
    best_goal_source = initial
    best_finish = initial.finish(target)
    termination = "queue_exhausted"

    while queue:
        now = monotonic()
        if on_progress is not None and now >= next_progress:
            on_progress(
                InventorySearchProgress(
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
            termination = "fuzzy_bound"
            break
        if max_expansions is not None and expanded >= max_expansions:
            termination = "expansion_limit"
            break

        expanded += 1
        candidates = promising_errands(
            gamestate,
            target,
            limit=feelers,
            price_horizon_multiplier=price_horizon_multiplier,
            queue_pops=queue_pops,
        )
        generated += len(candidates)

        for candidate in candidates:
            child = candidate.gamestate
            child_key = inventory_key(child)
            previous = best_state_by_inventory.get(child_key)
            if previous is not None and previous.age <= child.age:
                continue

            best_state_by_inventory[child_key] = child
            came_from[child] = (gamestate, candidate.purchases)
            relaxed += 1

            finished = child.finish(target)
            if finished.age < best_finish.age:
                best_finish = finished
                best_goal_source = child

            heappush(queue, (priority(child), next(serial), child))
            maximum_queue_size = max(maximum_queue_size, len(queue))

    errands = _reconstruct_errands(best_goal_source, came_from)
    if on_errand is not None:
        for errand in errands:
            on_errand(errand)

    stats = InventorySearchStats(
        elapsed_seconds=monotonic() - started_at,
        expanded=expanded,
        generated=generated,
        relaxed=relaxed,
        stale_skipped=stale_skipped,
        heuristic_evaluations=heuristic_evaluations,
        fuzzy_route_evaluations=heuristic.route_evaluations,
        checkpoint_tails=len(heuristic.shared_tails),
        maximum_queue_size=maximum_queue_size,
        termination=termination,
    )
    return InventorySearchResult(best_finish, errands, stats)

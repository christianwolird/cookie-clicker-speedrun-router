"""Dynamic programming for partitioning a fixed purchase order into errands."""

from itertools import groupby

from ..routes.replay import apply_errand
from ..game.actions import RouteAction


DEFAULT_MAX_ERRAND_SIZE = 100
DEFAULT_STATE_WIDTH = 10


def _bulk_clicks(actions, bulk_size):
    """Compress adjacent copies without changing the fixed purchase order."""
    clicks = []
    for (operation, item), group in groupby(actions, lambda action: (action.operation, action.item)):
        quantity = sum(action.quantity for action in group)
        if operation == "upgrade":
            clicks.extend(RouteAction(operation, item) for _ in range(quantity))
            continue
        while quantity:
            clicked = min(bulk_size, quantity)
            clicks.append(RouteAction(operation, item, clicked))
            quantity -= clicked
    return tuple(clicks)


def _partition_profiled_actions(initial, actions, max_errand_size, state_width):
    # A prefix can have several useful banks. Keep a bounded set rather than
    # declaring its earliest arrival universally best. Unreachable prefixes may
    # be skipped by a later bulk group, so only fail if the final prefix fails.
    states = [[(initial.copy(), ())]] + [[] for _ in actions]
    for end in range(1, len(actions) + 1):
        candidates = {}
        for size in range(1, min(max_errand_size, end) + 1):
            start = end - size
            clicks = _bulk_clicks(actions[start:end], initial.bulk_size)
            for ancestor, history in states[start]:
                try:
                    child, purchases = apply_errand(ancestor, clicks)
                except (KeyError, ValueError):
                    continue
                key = (child.bank, child.lifetime_cookies, child.handmade_cookies)
                previous = candidates.get(key)
                if previous is None or child.age < previous[0].age:
                    executed = tuple(RouteAction.from_purchase(purchase) for purchase in purchases)
                    candidates[key] = (child, history + (executed,))
        states[end] = sorted(candidates.values(), key=lambda candidate: candidate[0].age)[:state_width]
    if not states[-1]:
        raise ValueError(
            "No executable partition found for this purchase order within the errand search limits"
        )
    return states[-1][0][1]


def partition_contiguous_actions(
    initial_gamestate,
    actions,
    max_errand_size=DEFAULT_MAX_ERRAND_SIZE,
    state_width=DEFAULT_STATE_WIDTH,
):
    """Partition ``actions`` into executable contiguous errands.

    For each nonempty action prefix, consider every final errand containing up
    to ``max_errand_size`` actions. Extend the fastest saved solution for the
    preceding prefix, retain the candidate with the lowest resulting age, and
    reconstruct the chosen errands from predecessor links.

    The legacy model retains one state per prefix and excludes mixed sales.
    Profiled execution compiles fixed bulk clicks and keeps up to ``state_width``
    alternative banks per prefix. It is a bounded search, not an exact optimum.
    """
    if max_errand_size <= 0:
        raise ValueError("max_errand_size must be greater than zero")
    if state_width <= 0:
        raise ValueError("state_width must be greater than zero")

    actions = tuple(actions)
    if not initial_gamestate.legacy_errands:
        return _partition_profiled_actions(initial_gamestate, actions, max_errand_size, state_width)
    best_states = [initial_gamestate.copy()]
    predecessors = [None]
    final_errands = [None]

    for end in range(1, len(actions) + 1):
        candidates = []
        for size in range(1, min(max_errand_size, end) + 1):
            start = end - size
            errand = actions[start:end]
            try:
                child, _ = apply_errand(best_states[start], errand)
            except (KeyError, ValueError):
                continue
            candidates.append((child.age, size, start, child, errand))

        if not candidates:
            action = actions[end - 1]
            raise ValueError(
                f"No valid partition reaches action {end}: "
                f"{action.operation} {action.item}"
            )

        _, _, start, child, errand = min(
            candidates,
            key=lambda candidate: (candidate[0], candidate[1]),
        )
        best_states.append(child)
        predecessors.append(start)
        final_errands.append(tuple(errand))

    errands = []
    end = len(actions)
    while end:
        errands.append(final_errands[end])
        end = predecessors[end]
    errands.reverse()
    return tuple(errands)

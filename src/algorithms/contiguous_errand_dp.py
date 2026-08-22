"""Dynamic programming for partitioning a fixed purchase order into errands."""

from ..routes import apply_errand


ALGORITHM_NAME = "contiguous_errand_dp"
DEFAULT_MAX_ERRAND_SIZE = 100


def partition_contiguous_actions(
    initial_gamestate,
    actions,
    max_errand_size=DEFAULT_MAX_ERRAND_SIZE,
):
    """Return the fastest contiguous errand partition of ``actions``.

    For each nonempty action prefix, consider every final errand containing up
    to ``max_errand_size`` actions. Extend the fastest saved solution for the
    preceding prefix, retain the candidate with the lowest resulting age, and
    reconstruct the chosen errands from predecessor links.

    Invalid groups, including groups containing a sale and another action, are
    skipped. Exact ties prefer the smaller final errand.
    """
    if max_errand_size <= 0:
        raise ValueError("max_errand_size must be greater than zero")

    actions = tuple(actions)
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

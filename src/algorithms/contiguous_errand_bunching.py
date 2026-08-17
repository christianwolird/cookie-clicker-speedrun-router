from ..routes import apply_errand
from .scoring import age_score


ALGORITHM_NAME = "contiguous_errand_bunching"
DEFAULT_MAX_ERRAND_SIZE = 20


def _candidate_sizes(actions, start, max_errand_size):
    if actions[start].operation == "sell":
        return range(1, 2)

    end = min(len(actions), start + max_errand_size)
    for index in range(start, end):
        if actions[index].operation == "sell":
            end = index
            break
    return range(1, end - start + 1)


def bunch_contiguous_actions(
    initial_gamestate,
    actions,
    max_errand_size=DEFAULT_MAX_ERRAND_SIZE,
):
    """Greedily partition a fixed action order into age-scored errands.

    At each boundary, every valid contiguous prefix from one through
    ``max_errand_size`` actions is applied as one unordered errand. The prefix
    with the lowest age score becomes the next errand. Sales remain singleton
    because the gamestate model does not group sales with purchases.
    """
    if max_errand_size <= 0:
        raise ValueError("max_errand_size must be greater than zero")

    actions = tuple(actions)
    gamestate = initial_gamestate.copy()
    errands = []
    start = 0

    while start < len(actions):
        candidates = []
        for size in _candidate_sizes(actions, start, max_errand_size):
            errand = actions[start : start + size]
            try:
                child, _ = apply_errand(gamestate, errand)
            except (KeyError, ValueError):
                continue
            candidates.append(
                (age_score(gamestate, child), size, child, errand)
            )

        if not candidates:
            action = actions[start]
            raise ValueError(
                f"Action {start + 1} cannot begin a valid errand: "
                f"{action.operation} {action.item}"
            )

        _, size, gamestate, errand = min(
            candidates,
            # Prefer the smaller group if two prefixes have exactly the same
            # score. This keeps no-benefit grouping out of the stored route.
            key=lambda candidate: (candidate[0], candidate[1]),
        )
        errands.append(tuple(errand))
        start += size

    return tuple(errands)

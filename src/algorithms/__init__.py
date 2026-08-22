from . import errand_queueing, fuzzy_astar


DEFAULT_ALGORITHM = "errand_queueing"


ALGORITHMS = {
    "errand_queueing": errand_queueing.find_route,
    "fuzzy_astar": fuzzy_astar.find_route,
    "singleton_errands": errand_queueing.find_singleton_route,
}


def available_algorithms():
    return tuple(sorted(ALGORITHMS))


def get_algorithm(name):
    try:
        return ALGORITHMS[name]
    except KeyError as error:
        raise ValueError(f"Unknown algorithm: {name}") from error


__all__ = [
    "DEFAULT_ALGORITHM",
    "available_algorithms",
    "get_algorithm",
]

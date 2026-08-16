from dataclasses import dataclass
from typing import Callable

from . import age_scoring, naive_scoring
from .models import RouteResult


DEFAULT_ALGORITHM = "age_scoring"


@dataclass(frozen=True, slots=True)
class Algorithm:
    name: str
    description: str
    find_route: Callable


ALGORITHMS = {
    "age_scoring": Algorithm(
        "age_scoring",
        "greedy upgrade descendants scored by their effective acquisition time",
        age_scoring.find_route,
    ),
    "naive_scoring": Algorithm(
        "naive_scoring",
        "greedy upgrade descendants scored by their total sticker price",
        naive_scoring.find_route,
    ),
}


def available_algorithms():
    return tuple(sorted(ALGORITHMS))


def get_algorithm(name):
    try:
        return ALGORITHMS[name]
    except KeyError as error:
        raise ValueError(f"Unknown algorithm: {name}") from error


__all__ = [
    "Algorithm",
    "DEFAULT_ALGORITHM",
    "RouteResult",
    "available_algorithms",
    "get_algorithm",
]

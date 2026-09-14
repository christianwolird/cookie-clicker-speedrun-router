"""Run objectives, independent of game version and execution method."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Goal:
    name: str
    target: int


GOALS = {
    goal.name: goal for goal in (
        Goal("10k", 10_000),
        Goal("100k", 100_000),
        Goal("one_million", 1_000_000),
        Goal("one_billion", 1_000_000_000),
        Goal("heavenly_chip", 1_000_000_000_000),
    )
}


def available_goals():
    return tuple(GOALS)


def load_goal(name):
    try:
        return GOALS[name]
    except KeyError as error:
        raise ValueError(f"Unknown goal: {name}") from error


def legacy_goal(category, target):
    """Translate historical category labels without depending on config files."""
    if category == "heavenly_chip":
        return "heavenly_chip"
    return next(
        (goal.name for goal in GOALS.values() if goal.target == target),
        f"{target}_cookies",
    )

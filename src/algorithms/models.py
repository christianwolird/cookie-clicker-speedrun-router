from dataclasses import dataclass

from ..gamestate import Gamestate, Purchase


@dataclass(frozen=True, slots=True)
class RouteResult:
    final_gamestate: Gamestate
    purchases: tuple[Purchase, ...]

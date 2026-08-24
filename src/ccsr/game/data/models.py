"""Shared value types for every supported Cookie Clicker version."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Building:
    base_price: int
    base_cps: float


@dataclass(frozen=True, slots=True)
class Upgrade:
    price: int
    requirements: tuple[tuple[str, int], ...] = ()
    building: str | None = None
    cursor_multiplier: float = 1.0
    finger_add: float = 0.0
    production_multiplier: float = 1.0
    kitten_coefficient: float = 0.0
    mouse_cps_fraction: float = 0.0
    grandma_synergy: str | None = None
    cookies_required: float = 0.0
    handmade_required: float = 0.0

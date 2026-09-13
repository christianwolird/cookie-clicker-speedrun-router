"""Configuration loaders and run-state construction."""

from .achievement_curves import load_achievement_curve
from .categories import Category, available_categories, load_category
from .errand_profiles import (
    ErrandProfile, available_errand_profiles, load_errand_profile,
)
from .player_profiles import (
    PlayerProfile,
    available_player_profiles,
    load_player_profile,
)
from ..game.gamestate import Gamestate


def create_initial_gamestate(category, player, *, for_quickster=False, errand_profile=None):
    curve = load_achievement_curve(category.achievement_curve)
    gamestate = Gamestate(category.version, curve)
    if category.initial_state == "neverclick":
        gamestate.initialize_neverclick()
    gamestate.click_rate = (
        player.click_rate if category.clicking_enabled else 0.0
    )
    gamestate.errand_delay = 0.0 if for_quickster else player.errand_delay
    gamestate.action_delay = 0.0 if for_quickster else player.action_delay
    if errand_profile is not None:
        gamestate.bulk_size = errand_profile.bulk_size
        gamestate.selling_allowed = errand_profile.selling_allowed
        gamestate.legacy_errands = False
    gamestate.upgrades_allowed = category.upgrades_enabled
    return gamestate


__all__ = [
    "Category",
    "ErrandProfile",
    "available_errand_profiles",
    "load_errand_profile",
    "PlayerProfile",
    "available_categories",
    "available_player_profiles",
    "create_initial_gamestate",
    "load_achievement_curve",
    "load_category",
    "load_player_profile",
]

"""Configuration loaders and run-state construction."""

from .achievement_curves import load_achievement_curve
from .categories import Category, available_categories, load_category
from .player_profiles import (
    PlayerProfile,
    available_player_profiles,
    load_player_profile,
)
from ..game.gamestate import Gamestate


def create_initial_gamestate(category, player, *, for_quickster=False):
    curve = load_achievement_curve(category.achievement_curve)
    gamestate = Gamestate(category.version, curve)
    if category.initial_state == "neverclick":
        gamestate.initialize_neverclick()
    gamestate.click_rate = (
        player.click_rate if category.clicking_enabled else 0.0
    )
    gamestate.errand_delay = 0.0 if for_quickster else player.errand_delay
    gamestate.item_delay = 0.0 if for_quickster else player.item_delay
    gamestate.upgrades_allowed = category.upgrades_enabled
    return gamestate


__all__ = [
    "Category",
    "PlayerProfile",
    "available_categories",
    "available_player_profiles",
    "create_initial_gamestate",
    "load_achievement_curve",
    "load_category",
    "load_player_profile",
]

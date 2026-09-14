"""Configuration loaders and run-state construction."""

from .achievement_curves import load_achievement_curve
from .goals import Goal, available_goals, load_goal
from .route_profiles import RouteProfile, available_route_profiles, load_route_profile
from .errand_profiles import (
    ErrandProfile, available_errand_profiles, load_errand_profile,
)
from .player_profiles import (
    PlayerProfile,
    available_player_profiles,
    load_player_profile,
)
from ..game.gamestate import Gamestate


def create_initial_gamestate(route_profile, player=None, *, for_quickster=False, errand_profile=None):
    player = player or load_player_profile(route_profile.player_profile)
    errand_profile = errand_profile or load_errand_profile(route_profile.errand_profile)
    curve = load_achievement_curve(route_profile.achievement_curve)
    gamestate = Gamestate(route_profile.version, curve)
    if player.initial_state == "neverclick":
        gamestate.initialize_neverclick()
    gamestate.click_rate = player.click_rate
    gamestate.errand_delay = 0.0 if for_quickster else player.errand_delay
    gamestate.action_delay = 0.0 if for_quickster else player.action_delay
    gamestate.bulk_size = errand_profile.bulk_size
    gamestate.selling_allowed = errand_profile.selling_allowed
    gamestate.legacy_errands = False
    gamestate.upgrades_allowed = route_profile.upgrades_enabled
    return gamestate


__all__ = [
    "Goal",
    "RouteProfile",
    "available_goals",
    "load_goal",
    "available_route_profiles",
    "load_route_profile",
    "ErrandProfile",
    "available_errand_profiles",
    "load_errand_profile",
    "PlayerProfile",
    "available_player_profiles",
    "create_initial_gamestate",
    "load_achievement_curve",
    "load_player_profile",
]

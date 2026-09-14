"""Chosen game and execution settings for each category and click rate."""

from dataclasses import dataclass
from pathlib import Path

from .achievement_curves import load_achievement_curve
from .errand_profiles import load_errand_profile
from .goals import load_goal
from .player_profiles import load_player_profile
from ..game.data import SUPPORTED_VERSIONS


ROUTE_PROFILE_DIRECTORY = Path(__file__).resolve().parents[3] / "config/route_profiles"


@dataclass(frozen=True, slots=True)
class RouteProfile:
    name: str
    goal: str
    version: str
    player_profile: str
    errand_profile: str
    upgrades_enabled: bool = True
    achievement_curve: str | None = None

    @property
    def target(self):
        return load_goal(self.goal).target


def available_route_profiles(profile_directory=ROUTE_PROFILE_DIRECTORY):
    return tuple(sorted(path.stem for path in Path(profile_directory).glob("*.conf")))


def load_route_profile(name, profile_directory=ROUTE_PROFILE_DIRECTORY):
    directory = Path(profile_directory)
    path = directory / f"{name}.conf"
    if path.parent != directory or not path.is_file():
        raise ValueError(f"Unknown route profile: {name}")
    required = {"goal", "version", "player_profile", "errand_profile"}
    optional = {"upgrades_enabled", "achievement_curve"}
    values = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not value or key not in required | optional:
            raise ValueError(f"{path}:{number}: unknown or invalid setting: {line}")
        if key in values:
            raise ValueError(f"{path}:{number}: duplicate setting: {key}")
        values[key] = value
    missing = required - values.keys()
    if missing:
        raise ValueError(f"{path}: missing settings: {', '.join(sorted(missing))}")
    load_goal(values["goal"])
    if values["version"] not in SUPPORTED_VERSIONS:
        raise ValueError(f"{path}: unsupported version: {values['version']}")
    load_player_profile(values["player_profile"])
    load_errand_profile(values["errand_profile"])
    enabled = values.get("upgrades_enabled", "true").lower()
    if enabled not in {"true", "false"}:
        raise ValueError(f"{path}: upgrades_enabled must be true or false")
    curve = values.get("achievement_curve", "none")
    load_achievement_curve(curve)
    return RouteProfile(
        name=name, goal=values["goal"], version=values["version"],
        player_profile=values["player_profile"], errand_profile=values["errand_profile"],
        upgrades_enabled=enabled == "true",
        achievement_curve=None if curve == "none" else curve,
    )

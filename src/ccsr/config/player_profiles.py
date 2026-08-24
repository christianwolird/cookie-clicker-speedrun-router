"""Player execution-speed profiles."""

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PLAYER_PROFILE_DIRECTORY = PROJECT_ROOT / "config" / "player_profiles"


@dataclass(frozen=True, slots=True)
class PlayerProfile:
    name: str
    click_rate: float
    errand_delay: float
    item_delay: float


PARSERS = {
    "click_rate": float,
    "errand_delay": float,
    "item_delay": float,
}


def available_player_profiles(profile_directory=PLAYER_PROFILE_DIRECTORY):
    return tuple(
        sorted(path.stem for path in Path(profile_directory).glob("*.conf"))
    )


def load_player_profile(name, profile_directory=PLAYER_PROFILE_DIRECTORY):
    profile_directory = Path(profile_directory)
    path = profile_directory / f"{name}.conf"
    if path.parent != profile_directory or not path.is_file():
        raise ValueError(f"Unknown player profile: {name}")

    values = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or not value:
            raise ValueError(f"{path}:{line_number}: expected key = value")
        if key not in PARSERS:
            raise ValueError(f"{path}:{line_number}: unknown setting: {key}")
        if key in values:
            raise ValueError(f"{path}:{line_number}: duplicate setting: {key}")
        try:
            values[key] = PARSERS[key](value)
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: {key} {error}") from error

    missing = sorted(set(PARSERS) - values.keys())
    if missing:
        raise ValueError(f"{path}: missing settings: {', '.join(missing)}")
    for key, value in values.items():
        if value < 0:
            raise ValueError(f"{path}: {key} cannot be negative")
    return PlayerProfile(name=name, **values)

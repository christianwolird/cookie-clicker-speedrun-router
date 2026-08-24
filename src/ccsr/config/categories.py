"""Speedrun category configuration."""

from dataclasses import dataclass
from pathlib import Path

from ..game.data import SUPPORTED_VERSIONS
from .achievement_curves import load_achievement_curve


PROJECT_ROOT = Path(__file__).resolve().parents[3]
CATEGORY_DIRECTORY = PROJECT_ROOT / "config" / "categories"


@dataclass(frozen=True, slots=True)
class Category:
    name: str
    version: str
    target: int
    initial_state: str
    upgrades_enabled: bool
    clicking_enabled: bool
    achievement_curve: str | None


def _boolean(value):
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("must be true or false")


PARSERS = {
    "version": str,
    "target": int,
    "initial_state": str,
    "upgrades_enabled": _boolean,
    "clicking_enabled": _boolean,
    "achievement_curve": str,
}


def available_categories(category_directory=CATEGORY_DIRECTORY):
    return tuple(
        sorted(path.stem for path in Path(category_directory).glob("*.conf"))
    )


def load_category(name, category_directory=CATEGORY_DIRECTORY):
    category_directory = Path(category_directory)
    path = category_directory / f"{name}.conf"
    if path.parent != category_directory or not path.is_file():
        raise ValueError(f"Unknown category: {name}")

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

    required = set(PARSERS)
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(f"{path}: missing settings: {', '.join(missing)}")
    if values["version"] not in SUPPORTED_VERSIONS:
        raise ValueError(f"{path}: unsupported version: {values['version']}")
    if values["target"] <= 0:
        raise ValueError(f"{path}: target must be greater than zero")
    if values["initial_state"] not in {"fresh", "neverclick"}:
        raise ValueError(f"{path}: initial_state must be fresh or neverclick")
    curve_name = values["achievement_curve"]
    load_achievement_curve(curve_name)
    return Category(
        name=name,
        version=values["version"],
        target=values["target"],
        initial_state=values["initial_state"],
        upgrades_enabled=values["upgrades_enabled"],
        clicking_enabled=values["clicking_enabled"],
        achievement_curve=None if curve_name == "none" else curve_name,
    )

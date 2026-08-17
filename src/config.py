"""Category configuration shared by the generation CLI and tests."""

from pathlib import Path

from .algorithms import DEFAULT_ALGORITHM, available_algorithms
from .algorithms.errand_queueing import DEFAULT_QUEUE_POPS
from .data import DEFAULT_VERSION, SUPPORTED_VERSIONS
from .gamestate import (
    DEFAULT_CLICK_RATE,
    DEFAULT_ERRAND_DURATION,
    DEFAULT_PURCHASE_CLICK_RATE,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CATEGORY_DIRECTORY = PROJECT_ROOT / "categories"
LOCAL_ROUTE_DIRECTORY = PROJECT_ROOT / "routes" / "local"
DEFAULT_SETTINGS = {
    "algorithm": DEFAULT_ALGORITHM,
    "version": DEFAULT_VERSION,
    "target": 1_000_000,
    "click_rate": DEFAULT_CLICK_RATE,
    "errand_duration": DEFAULT_ERRAND_DURATION,
    "purchase_click_rate": DEFAULT_PURCHASE_CLICK_RATE,
    "errand_queue_depth": DEFAULT_QUEUE_POPS,
    "price_horizon_multiplier": 2.0,
    "initial_state": "fresh",
    "upgrades_enabled": True,
}


def _boolean(value):
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError("must be true or false")


CATEGORY_VALUE_PARSERS = {
    "algorithm": str,
    "version": str,
    "target": int,
    "click_rate": float,
    "errand_duration": float,
    "purchase_click_rate": float,
    "errand_queue_depth": int,
    "price_horizon_multiplier": float,
    "initial_state": str,
    "upgrades_enabled": _boolean,
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

    settings = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or not key or not value:
            raise ValueError(f"{path}:{line_number}: expected key = value")
        if key not in CATEGORY_VALUE_PARSERS:
            raise ValueError(f"{path}:{line_number}: unknown setting: {key}")
        if key in settings:
            raise ValueError(f"{path}:{line_number}: duplicate setting: {key}")
        try:
            settings[key] = CATEGORY_VALUE_PARSERS[key](value)
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: {key} {error}") from error

    validate_settings({**DEFAULT_SETTINGS, **settings}, source=path)
    return settings


def validate_settings(settings, source="settings"):
    if settings["version"] not in SUPPORTED_VERSIONS:
        raise ValueError(f"{source}: unsupported version: {settings['version']}")
    if settings["algorithm"] not in available_algorithms():
        raise ValueError(f"{source}: unknown algorithm: {settings['algorithm']}")
    if settings["initial_state"] not in {"fresh", "neverclick"}:
        raise ValueError(f"{source}: initial_state must be fresh or neverclick")
    bounds = (
        ("target", 0, False),
        ("click_rate", 0, True),
        ("errand_duration", 0, True),
        ("purchase_click_rate", 0, False),
        ("errand_queue_depth", 0, False),
        ("price_horizon_multiplier", 0, False),
    )
    for key, lower, inclusive in bounds:
        value = settings[key]
        valid = value >= lower if inclusive else value > lower
        if not valid:
            comparison = "at least" if inclusive else "greater than"
            raise ValueError(f"{source}: {key} must be {comparison} {lower}")


def local_route_path(destination):
    path = Path(destination)
    if path.suffix != ".route":
        raise ValueError("Route destination must end in .route")
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    path = path.resolve()
    if not path.is_relative_to(LOCAL_ROUTE_DIRECTORY.resolve()):
        raise ValueError("Route destination must be inside routes/local/")
    return path

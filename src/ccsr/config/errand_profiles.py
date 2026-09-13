"""Shop choices, independently of player execution speed."""

from dataclasses import dataclass
from pathlib import Path


ERRAND_PROFILE_DIRECTORY = Path(__file__).resolve().parents[3] / "config/errand_profiles"


@dataclass(frozen=True, slots=True)
class ErrandProfile:
    name: str
    bulk_size: int = 1
    selling_allowed: bool = False

    def __post_init__(self):
        if self.bulk_size not in (1, 10):
            raise ValueError("bulk_size must be 1 or 10")
        if not isinstance(self.selling_allowed, bool):
            raise ValueError("selling_allowed must be true or false")


def available_errand_profiles(profile_directory=ERRAND_PROFILE_DIRECTORY):
    return tuple(sorted(path.stem for path in Path(profile_directory).glob("*.conf")))


def load_errand_profile(name, profile_directory=ERRAND_PROFILE_DIRECTORY):
    directory = Path(profile_directory)
    path = directory / f"{name}.conf"
    if path.parent != directory or not path.is_file():
        raise ValueError(f"Unknown errand profile: {name}")
    values = {}
    for number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not separator or key not in {"bulk_size", "selling_allowed"}:
            raise ValueError(f"{path}:{number}: unknown or invalid setting: {line}")
        if key in values:
            raise ValueError(f"{path}:{number}: duplicate setting: {key}")
        if key == "bulk_size":
            try:
                values[key] = int(value)
            except ValueError as error:
                raise ValueError(f"{path}:{number}: invalid bulk_size") from error
        else:
            if value.lower() not in {"true", "false"}:
                raise ValueError(f"{path}:{number}: selling_allowed must be true or false")
            values[key] = value.lower() == "true"
    if values.keys() != {"bulk_size", "selling_allowed"}:
        raise ValueError(f"{path}: bulk_size and selling_allowed are required")
    return ErrandProfile(name, **values)

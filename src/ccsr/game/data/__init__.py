"""Version selection for the hand-written Cookie Clicker data catalogs."""

from . import v1_0466, v2_031
from .models import Building, Upgrade


DEFAULT_VERSION = "2.031"
VERSION_DATA = {
    v1_0466.VERSION: v1_0466,
    v2_031.VERSION: v2_031,
}
SUPPORTED_VERSIONS = tuple(VERSION_DATA)


def get_version_data(version):
    try:
        return VERSION_DATA[str(version)]
    except KeyError as error:
        supported = ", ".join(SUPPORTED_VERSIONS)
        raise ValueError(
            f"Unknown game version: {version}. Supported versions: {supported}"
        ) from error


__all__ = [
    "DEFAULT_VERSION",
    "SUPPORTED_VERSIONS",
    "Building",
    "Upgrade",
    "get_version_data",
]

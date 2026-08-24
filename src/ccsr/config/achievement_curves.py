"""Approximate lifetime-cookie to achievement-count curves."""

from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ACHIEVEMENT_CURVE_DIRECTORY = PROJECT_ROOT / "config" / "achievement_curves"


@dataclass(frozen=True, slots=True)
class AchievementCurve:
    name: str
    thresholds: tuple[float, ...]
    counts: tuple[int, ...]

    def count_at(self, lifetime_cookies):
        index = bisect_right(self.thresholds, lifetime_cookies) - 1
        return self.counts[index] if index >= 0 else 0


def available_achievement_curves(
    curve_directory=ACHIEVEMENT_CURVE_DIRECTORY,
):
    return tuple(
        sorted(path.stem for path in Path(curve_directory).glob("*.conf"))
    )


def load_achievement_curve(
    name,
    curve_directory=ACHIEVEMENT_CURVE_DIRECTORY,
):
    if name in {None, "none"}:
        return None
    curve_directory = Path(curve_directory)
    path = curve_directory / f"{name}.conf"
    if path.parent != curve_directory or not path.is_file():
        raise ValueError(f"Unknown achievement curve: {name}")

    points = []
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        threshold, separator, count = line.partition("=")
        if not separator:
            raise ValueError(f"{path}:{line_number}: expected cookies = count")
        try:
            point = (float(threshold.strip()), int(count.strip()))
        except ValueError as error:
            raise ValueError(
                f"{path}:{line_number}: cookies and count must be numeric"
            ) from error
        if point[0] < 0 or point[1] < 0:
            raise ValueError(f"{path}:{line_number}: values cannot be negative")
        points.append(point)

    if not points:
        raise ValueError(f"{path}: curve contains no points")
    points.sort()
    if len({threshold for threshold, _ in points}) != len(points):
        raise ValueError(f"{path}: duplicate cookie threshold")
    if any(left[1] > right[1] for left, right in zip(points, points[1:])):
        raise ValueError(f"{path}: achievement counts must not decrease")
    return AchievementCurve(
        name,
        tuple(point[0] for point in points),
        tuple(point[1] for point in points),
    )

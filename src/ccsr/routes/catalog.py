"""A read-only catalog rebuilt from saved route metadata and replay results."""

from dataclasses import asdict, dataclass, fields
from pathlib import Path

from ..config import (
    available_route_profiles, load_route_profile, load_player_profile, load_errand_profile,
)
from .format import load_route
from .layout import route_kind
from .replay import execute_route


@dataclass(frozen=True, slots=True)
class CatalogEntry:
    path: Path
    plan: object | None
    finish_seconds: float | None
    completed_errands: int | None
    error: str | None = None


def inspect_route(path):
    path = Path(path)
    plan = None
    try:
        plan = load_route(path)
        result = execute_route(plan)
        return CatalogEntry(path, plan, result.final_gamestate.age, len(result.errands))
    except (OSError, KeyError, ValueError, ArithmeticError) as error:
        return CatalogEntry(path, plan, None, None, str(error))


def scan_routes(directory):
    directory = Path(directory)
    if not directory.is_dir():
        raise ValueError(f"Route directory does not exist: {directory}")
    return tuple(inspect_route(path) for path in sorted(directory.rglob("*.route")))


def profile_details(profile):
    player = load_player_profile(profile.player_profile)
    errands = load_errand_profile(profile.errand_profile)
    return {
        **asdict(profile), "target": profile.target,
        "click_rate": player.click_rate, "initial_state": player.initial_state,
        "errand_delay": player.errand_delay, "action_delay": player.action_delay,
        "bulk_size": errands.bulk_size, "selling_allowed": errands.selling_allowed,
    }


def profile_catalog():
    return tuple(profile_details(load_route_profile(name)) for name in available_route_profiles())


def matches_profile(plan, details):
    """Match effective human settings, not a potentially stale profile label."""
    if plan is None or plan.for_quickster or plan.errand_profile is None:
        return False
    fields = (
        "goal", "target", "version", "click_rate", "initial_state", "errand_delay",
        "action_delay", "bulk_size", "selling_allowed", "upgrades_enabled", "achievement_curve",
    )
    return all(getattr(plan, field) == details[field] for field in fields)


def entry_details(entry, *, profiles=(), root=None):
    path = entry.path
    if root is not None:
        try:
            path = path.relative_to(root)
        except ValueError:
            pass
    if entry.plan is None:
        return {"path": str(path), "error": entry.error}
    plan = entry.plan
    metadata = {field.name: getattr(plan, field.name) for field in fields(plan) if field.name != "errands"}
    origin = (
        "community" if plan.algorithm == "community_route" or plan.source.startswith("dha spreadsheet:")
        else "generated" if plan.source == "this codebase" else "other"
    )
    return {
        **metadata, "path": str(path), "origin": origin,
        "route_type": entry.path.parent.name,
        "route_kind": route_kind(entry.path),
        "execution": "quickster" if plan.for_quickster else "human",
        "errand_model": "legacy_x1" if plan.errand_profile is None else "fixed_bulk_v1",
        "finish_seconds": entry.finish_seconds,
        "completed_errands": entry.completed_errands,
        "recorded_errands": len(plan.errands),
        "matching_profiles": [profile["name"] for profile in profiles if matches_profile(plan, profile)],
        "error": entry.error,
    }

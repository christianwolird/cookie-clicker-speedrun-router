"""Plain-text route parsing, validation, and serialization."""

from pathlib import Path
import re
from math import isfinite

from ..game.data import SUPPORTED_VERSIONS
from .models import RouteAction, RoutePlan


ROUTE_OPERATIONS = frozenset({"buy", "sell", "upgrade"})
COMMON_METADATA_FIELDS = {
    "name",
    "source",
    "category",
    "player_profile",
    "version",
    "target",
    "click_rate",
    "initial_state",
    "algorithm",
    "upgrades_enabled",
    "for_quickster",
}
DELAY_METADATA_FIELDS = {"errand_delay", "item_delay", "action_delay"}
ERRAND_METADATA_FIELDS = {"errand_profile", "bulk_size", "selling_allowed", "errand_model"}
OPTIONAL_METADATA_FIELDS = {
    *DELAY_METADATA_FIELDS,
    *ERRAND_METADATA_FIELDS,
    "errand_search_width",
    "max_errand_actions",
    "errand_state_width",
    "price_horizon_multiplier",
    "errand_queue_depth",
    "max_errand_size",
    "beam_width",
    "ruler_scale",
    "ruler_route",
    "beam_max_expansions",
}


def _parse_boolean(path, metadata, key):
    value = metadata[key].lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise ValueError(f"{path}: {key} must be true or false")


def _parse_action(path, line_number, line):
    operation, separator, item = line.partition(" ")
    if not separator or operation not in ROUTE_OPERATIONS:
        raise ValueError(f"{path}:{line_number}: invalid route action: {line}")
    quantity = 1
    match = re.fullmatch(r"(.+) x(\d+)", item)
    if match:
        item, quantity = match.group(1), int(match.group(2))
    try:
        return RouteAction(operation, item, quantity)
    except ValueError as error:
        raise ValueError(f"{path}:{line_number}: {error}") from error


def load_route(path):
    """Load and validate a ``.route`` file."""
    path = Path(path)
    metadata = {}
    markerless_actions = []
    errands = []
    current_errand = None
    route_started = False

    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line and not route_started:
            key, value = (part.strip() for part in line.split("=", 1))
            if not key or not value:
                raise ValueError(f"{path}:{line_number}: expected key = value")
            if key in metadata:
                raise ValueError(
                    f"{path}:{line_number}: duplicate metadata: {key}"
                )
            metadata[key] = value
            continue
        if line == "errand":
            route_started = True
            if markerless_actions:
                raise ValueError(
                    f"{path}: cannot mix markerless actions and errands"
                )
            if current_errand is not None:
                if not current_errand:
                    raise ValueError(f"{path}:{line_number}: empty errand")
                errands.append(tuple(current_errand))
            current_errand = []
            continue

        route_started = True
        action = _parse_action(path, line_number, line)
        if current_errand is None:
            markerless_actions.append(action)
        else:
            current_errand.append(action)

    if current_errand is not None:
        if not current_errand:
            raise ValueError(f"{path}: empty final errand")
        errands.append(tuple(current_errand))
    elif markerless_actions:
        errands = [(action,) for action in markerless_actions]

    missing = sorted(COMMON_METADATA_FIELDS - metadata.keys())
    if missing:
        raise ValueError(f"{path}: missing metadata: {', '.join(missing)}")
    unexpected = sorted(
        metadata.keys() - COMMON_METADATA_FIELDS - OPTIONAL_METADATA_FIELDS
    )
    if unexpected:
        raise ValueError(f"{path}: unknown metadata: {', '.join(unexpected)}")
    if not errands:
        raise ValueError(f"{path}: route contains no actions")

    version = metadata["version"]
    if version not in SUPPORTED_VERSIONS:
        raise ValueError(f"{path}: unsupported version: {version}")
    initial_state = metadata["initial_state"]
    if initial_state not in {"fresh", "neverclick"}:
        raise ValueError(f"{path}: unknown initial_state: {initial_state}")

    for_quickster = _parse_boolean(path, metadata, "for_quickster")
    present_delays = DELAY_METADATA_FIELDS & metadata.keys()
    if for_quickster:
        if present_delays:
            raise ValueError(
                f"{path}: Quickster routes cannot specify purchase delays"
            )
        errand_delay = 0.0
        action_delay = 0.0
    else:
        missing_delays = []
        if "errand_delay" not in metadata:
            missing_delays.append("errand_delay")
        if not {"item_delay", "action_delay"} & metadata.keys():
            missing_delays.append("action_delay")
        if missing_delays:
            raise ValueError(
                f"{path}: missing metadata: {', '.join(missing_delays)}"
            )
        errand_delay = float(metadata["errand_delay"])
        if {"item_delay", "action_delay"} <= metadata.keys():
            raise ValueError(f"{path}: specify action_delay or legacy item_delay, not both")
        action_delay = float(metadata.get("action_delay", metadata.get("item_delay")))

    present_errand_fields = ERRAND_METADATA_FIELDS & metadata.keys()
    if present_errand_fields and present_errand_fields != ERRAND_METADATA_FIELDS:
        raise ValueError(f"{path}: incomplete errand profile metadata")
    if present_errand_fields and metadata["errand_model"] != "fixed_bulk_v1":
        raise ValueError(f"{path}: unsupported errand_model")
    bulk_size = int(metadata.get("bulk_size", "1"))
    if bulk_size not in (1, 10):
        raise ValueError(f"{path}: bulk_size must be 1 or 10")
    if not present_errand_fields and any(action.quantity != 1 for errand in errands for action in errand):
        raise ValueError(f"{path}: bulk actions require errand profile metadata")

    def optional_int(key):
        return int(metadata[key]) if key in metadata else None

    def optional_float(key):
        return float(metadata[key]) if key in metadata else None

    plan = RoutePlan(
        name=metadata["name"],
        source=metadata["source"],
        category=metadata["category"],
        player_profile=metadata["player_profile"],
        version=version,
        target=int(metadata["target"]),
        click_rate=float(metadata["click_rate"]),
        initial_state=initial_state,
        algorithm=metadata["algorithm"],
        upgrades_enabled=_parse_boolean(path, metadata, "upgrades_enabled"),
        for_quickster=for_quickster,
        errands=tuple(errands),
        errand_delay=errand_delay,
        action_delay=action_delay,
        price_horizon_multiplier=optional_float("price_horizon_multiplier"),
        errand_queue_depth=optional_int("errand_queue_depth"),
        max_errand_size=optional_int("max_errand_size"),
        beam_width=optional_int("beam_width"),
        ruler_scale=optional_float("ruler_scale"),
        ruler_route=metadata.get("ruler_route"),
        beam_max_expansions=optional_int("beam_max_expansions"),
        errand_profile=metadata.get("errand_profile"),
        bulk_size=bulk_size,
        selling_allowed=_parse_boolean(path, metadata, "selling_allowed") if present_errand_fields else True,
        errand_search_width=optional_int("errand_search_width"),
        max_errand_actions=optional_int("max_errand_actions"),
        errand_state_width=optional_int("errand_state_width"),
    )
    if plan.target <= 0:
        raise ValueError(f"{path}: target must be greater than zero")
    if not isfinite(plan.click_rate) or plan.click_rate < 0:
        raise ValueError(f"{path}: click_rate cannot be negative")
    if any(not isfinite(value) or value < 0 for value in (plan.errand_delay, plan.action_delay)):
        raise ValueError(f"{path}: purchase delays cannot be negative")
    positive_fields = {
        "price_horizon_multiplier": plan.price_horizon_multiplier,
        "errand_queue_depth": plan.errand_queue_depth,
        "max_errand_size": plan.max_errand_size,
        "beam_width": plan.beam_width,
        "beam_max_expansions": plan.beam_max_expansions,
        "errand_search_width": plan.errand_search_width,
        "max_errand_actions": plan.max_errand_actions,
        "errand_state_width": plan.errand_state_width,
    }
    for key, value in positive_fields.items():
        if value is not None and value <= 0:
            raise ValueError(f"{path}: {key} must be greater than zero")
    if plan.ruler_scale is not None and plan.ruler_scale < 0:
        raise ValueError(f"{path}: ruler_scale cannot be negative")
    _validate_profile_actions(plan)
    if plan.for_quickster and any(len(errand) != 1 for errand in plan.errands):
        raise ValueError(f"{path}: Quickster routes require single-transaction errands")
    return plan


def _validate_profile_actions(plan):
    if plan.errand_profile is None:
        return
    for action in plan.actions:
        if action.quantity > plan.bulk_size:
            raise ValueError("Action quantity exceeds the route's fixed bulk size")
        if action.operation == "sell" and not plan.selling_allowed:
            raise ValueError("Route contains sales but its errand profile disables selling")


def write_route(
    path,
    plan,
    *,
    comment=None,
    explicit_errands=True,
    overwrite=False,
):
    """Serialize a route plan in the canonical plain-text format."""
    path = Path(path)
    if path.suffix != ".route":
        raise ValueError("Route destination must end in .route")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Route already exists: {path}")
    _validate_profile_actions(plan)
    if plan.bulk_size not in (1, 10):
        raise ValueError("bulk_size must be 1 or 10")
    if plan.errand_profile is None and (plan.bulk_size != 1 or any(
        action.quantity != 1 for action in plan.actions
    )):
        raise ValueError("Bulk actions require errand profile metadata")
    if plan.for_quickster and any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Quickster routes require single-transaction errands")
    if not explicit_errands and any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Markerless routes require single-transaction errands")

    lines = []
    if comment:
        lines.append(f"# {comment}")
    lines.extend(
        [
            f"name = {plan.name}",
            f"source = {plan.source}",
            f"category = {plan.category}",
            f"player_profile = {plan.player_profile}",
            f"version = {plan.version}",
            f"target = {plan.target}",
            f"click_rate = {plan.click_rate:g}",
            f"initial_state = {plan.initial_state}",
            f"algorithm = {plan.algorithm}",
            f"upgrades_enabled = {str(plan.upgrades_enabled).lower()}",
            f"for_quickster = {str(plan.for_quickster).lower()}",
        ]
    )
    if not plan.for_quickster:
        lines.extend(
            [
                f"errand_delay = {float(plan.errand_delay)}",
                f"action_delay = {float(plan.action_delay)}",
            ]
        )
    if plan.errand_profile is not None:
        lines.extend([
            "errand_model = fixed_bulk_v1",
            f"errand_profile = {plan.errand_profile}",
            f"bulk_size = {plan.bulk_size}",
            f"selling_allowed = {str(plan.selling_allowed).lower()}",
        ])
    optional = (
        ("price_horizon_multiplier", plan.price_horizon_multiplier),
        ("errand_queue_depth", plan.errand_queue_depth),
        ("max_errand_size", plan.max_errand_size),
        ("beam_width", plan.beam_width),
        ("ruler_scale", plan.ruler_scale),
        ("ruler_route", plan.ruler_route),
        ("beam_max_expansions", plan.beam_max_expansions),
        ("errand_search_width", plan.errand_search_width),
        ("max_errand_actions", plan.max_errand_actions),
        ("errand_state_width", plan.errand_state_width),
    )
    for key, value in optional:
        if value is not None:
            rendered = f"{value:g}" if isinstance(value, float) else value
            lines.append(f"{key} = {rendered}")
    lines.append("")

    for errand in plan.errands:
        if explicit_errands:
            lines.append("errand")
        lines.extend(map(str, errand))
        if explicit_errands:
            lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n")
    return path

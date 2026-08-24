"""Plain-text route parsing, validation, and serialization."""

from pathlib import Path

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
DELAY_METADATA_FIELDS = {"errand_delay", "item_delay"}
OPTIONAL_METADATA_FIELDS = {
    *DELAY_METADATA_FIELDS,
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
    return RouteAction(operation, item)


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
        item_delay = 0.0
    else:
        missing_delays = sorted(DELAY_METADATA_FIELDS - metadata.keys())
        if missing_delays:
            raise ValueError(
                f"{path}: missing metadata: {', '.join(missing_delays)}"
            )
        errand_delay = float(metadata["errand_delay"])
        item_delay = float(metadata["item_delay"])

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
        item_delay=item_delay,
        price_horizon_multiplier=optional_float("price_horizon_multiplier"),
        errand_queue_depth=optional_int("errand_queue_depth"),
        max_errand_size=optional_int("max_errand_size"),
        beam_width=optional_int("beam_width"),
        ruler_scale=optional_float("ruler_scale"),
        ruler_route=metadata.get("ruler_route"),
        beam_max_expansions=optional_int("beam_max_expansions"),
    )
    if plan.target <= 0:
        raise ValueError(f"{path}: target must be greater than zero")
    if plan.click_rate < 0:
        raise ValueError(f"{path}: click_rate cannot be negative")
    if plan.errand_delay < 0 or plan.item_delay < 0:
        raise ValueError(f"{path}: purchase delays cannot be negative")
    positive_fields = {
        "price_horizon_multiplier": plan.price_horizon_multiplier,
        "errand_queue_depth": plan.errand_queue_depth,
        "max_errand_size": plan.max_errand_size,
        "beam_width": plan.beam_width,
        "beam_max_expansions": plan.beam_max_expansions,
    }
    for key, value in positive_fields.items():
        if value is not None and value <= 0:
            raise ValueError(f"{path}: {key} must be greater than zero")
    if plan.ruler_scale is not None and plan.ruler_scale < 0:
        raise ValueError(f"{path}: ruler_scale cannot be negative")
    if plan.for_quickster and any(len(errand) != 1 for errand in plan.errands):
        raise ValueError(f"{path}: Quickster routes require single-item errands")
    return plan


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
    if plan.for_quickster and any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Quickster routes require single-item errands")
    if not explicit_errands and any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Markerless routes require single-item errands")

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
                f"item_delay = {float(plan.item_delay)}",
            ]
        )
    optional = (
        ("price_horizon_multiplier", plan.price_horizon_multiplier),
        ("errand_queue_depth", plan.errand_queue_depth),
        ("max_errand_size", plan.max_errand_size),
        ("beam_width", plan.beam_width),
        ("ruler_scale", plan.ruler_scale),
        ("ruler_route", plan.ruler_route),
        ("beam_max_expansions", plan.beam_max_expansions),
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

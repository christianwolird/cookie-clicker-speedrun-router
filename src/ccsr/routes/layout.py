"""Route types name directories; route kinds prefix filenames."""

from pathlib import Path


ROUTES_DIRECTORY = Path(__file__).resolve().parents[3] / "routes"
ROUTE_KINDS = frozenset({
    "community_quickster", "community_errandified", "generated_greedy", "generated_beam",
})


def route_kind(path):
    return next((kind for kind in ROUTE_KINDS
                 if Path(path).stem == kind or Path(path).stem.startswith(kind + "_")), None)


def community_route_type(goal, click_rate, initial_state="fresh"):
    if initial_state == "neverclick":
        return "neverclick-0cps"
    types = {
        ("one_billion", 10): "hardcore-10cps",
        ("heavenly_chip", 15): "heavenly-chip-15cps",
        ("one_million", 10): "million-10cps",
        ("one_million", 15): "million-15cps",
        ("one_million", 200): "million-200cps",
    }
    try:
        return types[goal, click_rate]
    except KeyError as error:
        raise ValueError(f"No community route type for {goal} at {click_rate:g} CPS") from error


def generated_route_path(destination, route_type, kind, root=ROUTES_DIRECTORY):
    if kind not in ROUTE_KINDS or not kind.startswith("generated_"):
        raise ValueError(f"Unknown generated route kind: {kind}")
    if not route_type or Path(route_type).name != route_type or route_type in {".", ".."}:
        raise ValueError("Invalid route type")
    directory = Path(root).resolve() / route_type
    path = Path(destination)
    if path.suffix != ".route":
        raise ValueError("Route destination must end in .route")
    path = (path if path.is_absolute() else directory / path).resolve()
    if path.parent != directory:
        raise ValueError(f"Route destination must be directly inside {directory}")
    existing_kind = route_kind(path)
    if existing_kind and existing_kind != kind:
        raise ValueError(f"Route filename must use the {kind} prefix")
    if not existing_kind:
        path = path.with_name(f"{kind}_{path.name}")
    return path

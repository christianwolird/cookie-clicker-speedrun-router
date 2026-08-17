"""Plain-text route files and deterministic route replay."""

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .data import SUPPORTED_VERSIONS
from .gamestate import Gamestate, Purchase


ROUTE_OPERATIONS = frozenset({"buy", "sell", "upgrade"})
COMMON_METADATA_FIELDS = {
    "name",
    "source",
    "version",
    "target",
    "click_rate",
    "initial_state",
    "algorithm",
    "errand_duration",
    "purchase_click_rate",
    "upgrades_enabled",
    "errands_enabled",
}
OPTIONAL_METADATA_FIELDS = {"errand_queue_depth", "max_errand_size"}


@dataclass(frozen=True, slots=True)
class RouteAction:
    operation: str
    item: str

    @classmethod
    def from_purchase(cls, purchase):
        return cls(purchase.operation, purchase.item)

    def __str__(self):
        return f"{self.operation} {self.item}"


@dataclass(frozen=True, slots=True)
class RoutePlan:
    name: str
    source: str
    version: str
    target: int
    click_rate: float
    initial_state: str
    algorithm: str
    errand_duration: float
    purchase_click_rate: float
    upgrades_enabled: bool
    errands_enabled: bool
    errands: tuple[tuple[RouteAction, ...], ...]
    errand_queue_depth: int | None = None
    max_errand_size: int | None = None

    @property
    def actions(self):
        return tuple(action for errand in self.errands for action in errand)


@dataclass(frozen=True, slots=True)
class RouteResult:
    final_gamestate: Gamestate
    errands: tuple[tuple[Purchase, ...], ...]


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
    """Load and validate a ``.route`` file.

    Markerless action lists are interpreted as singleton errands. This is the
    canonical representation used for community routes whose grouping was not
    recorded by their authors.
    """
    path = Path(path)
    metadata = {}
    singleton_actions = []
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
                raise ValueError(
                    f"{path}:{line_number}: expected key = value"
                )
            if key in metadata:
                raise ValueError(
                    f"{path}:{line_number}: duplicate metadata: {key}"
                )
            metadata[key] = value
            continue
        if line == "errand":
            route_started = True
            if singleton_actions:
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
            singleton_actions.append(action)
        else:
            current_errand.append(action)

    if current_errand is not None:
        if not current_errand:
            raise ValueError(f"{path}: empty final errand")
        errands.append(tuple(current_errand))
    elif singleton_actions:
        errands = [(action,) for action in singleton_actions]

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

    target = int(metadata["target"])
    click_rate = float(metadata["click_rate"])
    errand_duration = float(metadata["errand_duration"])
    purchase_click_rate = float(metadata["purchase_click_rate"])
    upgrades_enabled = _parse_boolean(path, metadata, "upgrades_enabled")
    errands_enabled = _parse_boolean(path, metadata, "errands_enabled")
    errand_queue_depth = (
        int(metadata["errand_queue_depth"])
        if "errand_queue_depth" in metadata
        else None
    )
    max_errand_size = (
        int(metadata["max_errand_size"])
        if "max_errand_size" in metadata
        else None
    )

    if target <= 0:
        raise ValueError(f"{path}: target must be greater than zero")
    if click_rate < 0:
        raise ValueError(f"{path}: click_rate cannot be negative")
    if errand_duration < 0:
        raise ValueError(f"{path}: errand_duration cannot be negative")
    if purchase_click_rate <= 0:
        raise ValueError(
            f"{path}: purchase_click_rate must be greater than zero"
        )
    if errand_queue_depth is not None and errand_queue_depth <= 0:
        raise ValueError(
            f"{path}: errand_queue_depth must be greater than zero"
        )
    if max_errand_size is not None and max_errand_size <= 0:
        raise ValueError(
            f"{path}: max_errand_size must be greater than zero"
        )
    if errand_queue_depth is not None and max_errand_size is not None:
        raise ValueError(
            f"{path}: route cannot have both errand search parameters"
        )
    if not errands_enabled and any(len(errand) != 1 for errand in errands):
        raise ValueError(
            f"{path}: disabled errands require singleton route groups"
        )

    return RoutePlan(
        name=metadata["name"],
        source=metadata["source"],
        version=version,
        target=target,
        click_rate=click_rate,
        initial_state=initial_state,
        algorithm=metadata["algorithm"],
        errand_duration=errand_duration,
        purchase_click_rate=purchase_click_rate,
        upgrades_enabled=upgrades_enabled,
        errands_enabled=errands_enabled,
        errands=tuple(errands),
        errand_queue_depth=errand_queue_depth,
        max_errand_size=max_errand_size,
    )


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
    if not explicit_errands and any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Markerless routes must contain singleton errands")

    lines = []
    if comment:
        lines.append(f"# {comment}")
    lines.extend(
        [
            f"name = {plan.name}",
            f"source = {plan.source}",
            f"version = {plan.version}",
            f"target = {plan.target}",
            f"click_rate = {plan.click_rate:g}",
            f"initial_state = {plan.initial_state}",
            f"algorithm = {plan.algorithm}",
            f"errand_duration = {float(plan.errand_duration)}",
            f"purchase_click_rate = {float(plan.purchase_click_rate)}",
            f"upgrades_enabled = {str(plan.upgrades_enabled).lower()}",
            f"errands_enabled = {str(plan.errands_enabled).lower()}",
        ]
    )
    if plan.errand_queue_depth is not None:
        lines.append(f"errand_queue_depth = {plan.errand_queue_depth}")
    if plan.max_errand_size is not None:
        lines.append(f"max_errand_size = {plan.max_errand_size}")
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


def initial_gamestate(
    plan,
    *,
    version=None,
    errand_duration=None,
    purchase_click_rate=None,
):
    gamestate = Gamestate(version or plan.version)
    if plan.initial_state == "neverclick":
        gamestate.initialize_neverclick()
    gamestate.click_rate = plan.click_rate
    gamestate.upgrades_allowed = plan.upgrades_enabled
    gamestate.errand_duration = (
        plan.errand_duration if errand_duration is None else errand_duration
    )
    gamestate.purchase_click_rate = (
        plan.purchase_click_rate
        if purchase_click_rate is None
        else purchase_click_rate
    )
    return gamestate


def apply_errand(gamestate, actions):
    """Apply route actions to a child gamestate and return its purchase rows."""
    child = gamestate.copy()
    sales = [action for action in actions if action.operation == "sell"]
    if sales:
        if len(actions) != 1:
            raise ValueError("Sales cannot share an errand with other actions")
        purchases = child.sell_building(sales[0].item)
        return child, purchases

    upgrades = [
        action.item for action in actions if action.operation == "upgrade"
    ]
    if len(upgrades) != len(set(upgrades)):
        raise ValueError("An upgrade cannot occur twice in one errand")
    purchases = child.purchase_errand(
        Counter(
            action.item for action in actions if action.operation == "buy"
        ),
        upgrades,
    )
    return child, purchases


def execute_route(
    plan,
    version=None,
    on_errand=None,
    *,
    errand_duration=None,
    purchase_click_rate=None,
):
    """Replay a route until its target is reached."""
    gamestate = initial_gamestate(
        plan,
        version=version,
        errand_duration=errand_duration,
        purchase_click_rate=purchase_click_rate,
    )
    completed_errands = []

    for number, actions in enumerate(plan.errands, 1):
        try:
            child, purchases = apply_errand(gamestate, actions)
        except (KeyError, ValueError) as error:
            raise ValueError(f"Errand {number}: {error}") from error

        # The target is reached while saving, so this errand never occurs.
        if actions[0].operation != "sell" and (
            child.lifetime_cookies >= plan.target
        ):
            break
        completed_errands.append(purchases)
        if on_errand is not None:
            on_errand(purchases)
        gamestate = child

    return RouteResult(gamestate.finish(plan.target), tuple(completed_errands))


def action_errands(result):
    return tuple(
        tuple(RouteAction.from_purchase(purchase) for purchase in errand)
        for errand in result.errands
    )

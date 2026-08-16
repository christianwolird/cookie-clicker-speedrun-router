import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from make_route import LivePurchaseTable, live_item_width, print_result
from src.algorithms import RouteResult
from src.data import SUPPORTED_VERSIONS
from src.gamestate import (
    DEFAULT_ERRAND_DURATION,
    DEFAULT_PURCHASE_CLICK_RATE,
    Gamestate,
)


@dataclass(frozen=True, slots=True)
class RouteAction:
    operation: str
    item: str


@dataclass(frozen=True, slots=True)
class RoutePlan:
    name: str
    source: str
    version: str
    target: int
    click_rate: float
    initial_state: str
    actions: tuple[RouteAction, ...]


ROUTE_METADATA_FIELDS = {
    "name",
    "source",
    "version",
    "target",
    "click_rate",
    "initial_state",
}


def load_route(path):
    path = Path(path)
    metadata = {}
    actions = []

    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line and not actions:
            key, value = line.split("=", 1)
            metadata[key.strip()] = value.strip()
            continue

        operation, separator, item = line.partition(" ")
        if not separator or operation not in {"buy", "sell", "upgrade"}:
            raise ValueError(f"{path}:{line_number}: invalid route action: {line}")
        actions.append(RouteAction(operation, item))

    missing = sorted(ROUTE_METADATA_FIELDS - metadata.keys())
    if missing:
        raise ValueError(f"{path}: missing metadata: {', '.join(missing)}")
    unexpected = sorted(metadata.keys() - ROUTE_METADATA_FIELDS)
    if unexpected:
        raise ValueError(f"{path}: unknown metadata: {', '.join(unexpected)}")

    initial_state = metadata.get("initial_state", "fresh")
    if initial_state not in {"fresh", "neverclick"}:
        raise ValueError(f"{path}: unknown initial_state: {initial_state}")

    return RoutePlan(
        name=metadata["name"],
        source=metadata["source"],
        version=metadata["version"],
        target=int(metadata["target"]),
        click_rate=float(metadata["click_rate"]),
        initial_state=initial_state,
        actions=tuple(actions),
    )


def execute_route(
    plan,
    version=None,
    on_purchase=None,
    *,
    errand_duration=DEFAULT_ERRAND_DURATION,
    purchase_click_rate=DEFAULT_PURCHASE_CLICK_RATE,
):
    gamestate = Gamestate(version or plan.version)
    if plan.initial_state == "neverclick":
        gamestate.initialize_neverclick()
    gamestate.click_rate = plan.click_rate
    gamestate.errand_duration = errand_duration
    gamestate.purchase_click_rate = purchase_click_rate
    purchases = []

    for step, action in enumerate(plan.actions, 1):
        if gamestate.lifetime_cookies >= plan.target:
            break
        try:
            # Flat route files do not record errand groups yet, so each buy or
            # upgrade is replayed independently and creates a child. Sales keep
            # their legacy instantaneous-credit behavior for now.
            child = gamestate.copy()
            if action.operation == "buy":
                child.purchase_building(action.item)
            elif action.operation == "sell":
                child.sell_building(action.item)
            else:
                child.purchase_upgrade(action.item)
        except (KeyError, ValueError) as error:
            raise ValueError(
                f"Step {step} ({action.operation} {action.item}): {error}"
            ) from error

        # If saving for this purchase reaches the category target first, the
        # run ends without making that purchase, just as make_route.py does.
        if (
            action.operation != "sell"
            and child.lifetime_cookies >= plan.target
        ):
            break
        purchases.append(child.last_purchase)
        if on_purchase is not None:
            on_purchase(child.last_purchase)
        gamestate = child

    return RouteResult(gamestate.finish(plan.target), tuple(purchases))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay a purchase route")
    parser.add_argument("route_file")
    parser.add_argument(
        "--version",
        choices=SUPPORTED_VERSIONS,
        help="override the game version stored in the route file",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print purchases as the route is replayed",
    )
    parser.add_argument(
        "--errand-duration",
        type=float,
        default=DEFAULT_ERRAND_DURATION,
        help=(
            "fixed hand-clicking pause for a shop trip "
            f"(default: {DEFAULT_ERRAND_DURATION:g})"
        ),
    )
    parser.add_argument(
        "--purchase-click-rate",
        type=float,
        default=DEFAULT_PURCHASE_CLICK_RATE,
        help=(
            "items purchased per second during an errand "
            f"(default: {DEFAULT_PURCHASE_CLICK_RATE:g})"
        ),
    )
    args = parser.parse_args(argv)
    if args.errand_duration < 0:
        parser.error("--errand-duration cannot be negative")
    if args.purchase_click_rate <= 0:
        parser.error("--purchase-click-rate must be greater than zero")

    plan = load_route(args.route_file)
    initial_gamestate = Gamestate(args.version or plan.version)
    live_table = (
        LivePurchaseTable(live_item_width(initial_gamestate))
        if args.verbose
        else None
    )
    print(f"Replaying route to {plan.target:,} cookies...", flush=True)
    result = execute_route(
        plan,
        args.version,
        on_purchase=live_table.print_purchase if live_table else None,
        errand_duration=args.errand_duration,
        purchase_click_rate=args.purchase_click_rate,
    )
    if live_table and live_table.count:
        print()
    print_result(result, plan.target, include_table=False)


if __name__ == "__main__":
    main()

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from make_route import LivePurchaseTable, RouteResult, live_item_width, print_result
from src.data import SUPPORTED_VERSIONS
from src.game import Game


@dataclass(frozen=True, slots=True)
class RouteAction:
    operation: str
    item: str
    tier: int | None = None


@dataclass(frozen=True, slots=True)
class RoutePlan:
    name: str
    source: str
    version: str
    target: int
    click_rate: float
    purchase_delay: float
    initial_state: str
    allow_upgrades: bool
    actions: tuple[RouteAction, ...]


def _boolean(value, key):
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{key} must be true or false")


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
        if operation == "upgrade":
            family, separator, tier = item.rpartition(" ")
            if not separator or not tier.isdigit():
                raise ValueError(
                    f"{path}:{line_number}: upgrade actions require a numeric tier"
                )
            actions.append(RouteAction(operation, family, int(tier)))
        else:
            actions.append(RouteAction(operation, item))

    required = {"name", "source", "target", "click_rate"}
    missing = sorted(required - metadata.keys())
    version = metadata.get("version", metadata.get("profile"))
    if version is None:
        missing.append("version")
    if missing:
        raise ValueError(f"{path}: missing metadata: {', '.join(missing)}")

    initial_state = metadata.get("initial_state", "fresh")
    if initial_state not in {"fresh", "neverclick"}:
        raise ValueError(f"{path}: unknown initial_state: {initial_state}")

    return RoutePlan(
        name=metadata["name"],
        source=metadata["source"],
        version=version,
        target=int(metadata["target"]),
        click_rate=float(metadata["click_rate"]),
        purchase_delay=float(metadata.get("purchase_delay", 0.5)),
        initial_state=initial_state,
        allow_upgrades=_boolean(metadata.get("allow_upgrades", "true"), "allow_upgrades"),
        actions=tuple(actions),
    )


def execute_route(plan, version=None, on_purchase=None):
    game = Game(version or plan.version)
    if plan.initial_state == "neverclick":
        game.initialize_neverclick()
    game.clickrate = plan.click_rate
    game.purchase_delay = plan.purchase_delay
    game.allow_upgrades = plan.allow_upgrades
    purchases = []

    for step, action in enumerate(plan.actions, 1):
        if game.cookies >= plan.target:
            break
        try:
            child = game.copy()
            if action.operation == "buy":
                child.purchase_building(action.item)
            elif action.operation == "sell":
                child.sell_building(action.item)
            else:
                upgrades = game.upgrade_families.get(action.item, ())
                if (
                    action.tier is None
                    or action.tier < 1
                    or action.tier > len(upgrades)
                ):
                    raise ValueError(
                        f"Unknown {action.item} upgrade tier: {action.tier}"
                    )
                child.purchase_upgrade(upgrades[action.tier - 1])
        except (KeyError, ValueError) as error:
            raise ValueError(
                f"Step {step} ({action.operation} {action.item}): {error}"
            ) from error

        # If saving for this purchase reaches the category target first, the
        # run ends without making that purchase, just as make_route.py does.
        if action.operation != "sell" and child.cookies >= plan.target:
            break
        purchases.append(child.last_purchase)
        if on_purchase is not None:
            on_purchase(child.last_purchase)
        game = child

    return RouteResult(game.finish(plan.target), tuple(purchases))


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
    args = parser.parse_args(argv)

    plan = load_route(args.route_file)
    game = Game(args.version or plan.version)
    live_table = LivePurchaseTable(live_item_width(game)) if args.verbose else None
    print(f"Replaying route to {plan.target:,} cookies...", flush=True)
    result = execute_route(
        plan,
        args.version,
        on_purchase=live_table.print_purchase if live_table else None,
    )
    if live_table and live_table.count:
        print()
    print_result(result, plan.target, include_table=False)


if __name__ == "__main__":
    main()

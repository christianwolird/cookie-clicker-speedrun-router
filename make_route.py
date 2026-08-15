#!/usr/bin/env python3

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parent
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.data import DEFAULT_VERSION, SUPPORTED_VERSIONS
from src.game import Game, Purchase, purchase_score


ONE_MILLION = 1_000_000
LIVE_BUILDING_NUMBER = "0000"
CATEGORY_DIRECTORY = REPOSITORY / "categories"
LOCAL_ROUTE_DIRECTORY = REPOSITORY / "routes" / "local"
DEFAULT_SETTINGS = {
    "version": DEFAULT_VERSION,
    "target": ONE_MILLION,
    "click_rate": 10.0,
    "purchase_delay": 0.5,
    "price_cutoff_multiplier": 2.0,
    "initial_state": "fresh",
    "allow_upgrades": True,
}


def _boolean(value, key):
    normalized = value.lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise ValueError(f"{key} must be true or false")


CATEGORY_VALUE_PARSERS = {
    "version": str,
    "target": int,
    "click_rate": float,
    "purchase_delay": float,
    "price_cutoff_multiplier": float,
    "initial_state": str,
    "allow_upgrades": lambda value: _boolean(value, "allow_upgrades"),
}


def available_categories(category_directory=CATEGORY_DIRECTORY):
    return tuple(sorted(path.stem for path in Path(category_directory).glob("*.conf")))


def load_category(name, category_directory=CATEGORY_DIRECTORY):
    category_directory = Path(category_directory)
    path = category_directory / f"{name}.conf"
    if path.parent != category_directory or not path.is_file():
        raise ValueError(f"Unknown category: {name}")

    settings = {}
    for line_number, raw_line in enumerate(path.read_text().splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if not separator or not key or not value:
            raise ValueError(f"{path}:{line_number}: expected key = value")
        if key not in CATEGORY_VALUE_PARSERS:
            raise ValueError(f"{path}:{line_number}: unknown setting: {key}")
        if key in settings:
            raise ValueError(f"{path}:{line_number}: duplicate setting: {key}")
        try:
            settings[key] = CATEGORY_VALUE_PARSERS[key](value)
        except ValueError as error:
            raise ValueError(f"{path}:{line_number}: {error}") from error

    if settings.get("version", DEFAULT_VERSION) not in SUPPORTED_VERSIONS:
        raise ValueError(f"{path}: unsupported version: {settings['version']}")
    if settings.get("initial_state", "fresh") not in {"fresh", "neverclick"}:
        raise ValueError(
            f"{path}: initial_state must be fresh or neverclick"
        )
    return settings


def format_time(seconds):
    tenths = round(seconds * 10)
    minutes, remaining_tenths = divmod(tenths, 600)
    return f"{minutes}:{remaining_tenths / 10:04.1f}"


def top_child(parent, target):
    finish_without_purchase = parent.finish(target).age
    candidates = []

    for candidate in parent.children(cookie_limit=target):
        child = candidate.game
        # Reaching the target while saving means the purchase never happens.
        if child.cookies >= target:
            continue
        # Near the end, do not buy an item that delays the target even if it
        # would be locally first among a longer, no-longer-useful purchase list.
        if child.finish(target).age >= finish_without_purchase:
            continue
        candidates.append(candidate)

    return min(
        candidates,
        key=lambda candidate: purchase_score(parent, candidate.game),
        default=None,
    )


@dataclass(frozen=True, slots=True)
class RouteResult:
    game: Game
    purchases: tuple[Purchase, ...]


def find_route(start, target=ONE_MILLION, on_purchase=None):
    """Greedily take the locally optimal atomic purchase until the target."""
    game = start.copy()
    purchases = []
    while game.cookies < target:
        candidate = top_child(game, target)
        if candidate is None:
            break
        for purchase in candidate.purchases:
            purchases.append(purchase)
            if on_purchase is not None:
                on_purchase(purchase)
        game = candidate.game
    return RouteResult(game.finish(target), tuple(purchases))


def purchase_table_header(item_width):
    header = (
        f"{'#':>3}  {'Item':<{item_width}}  "
        f"{'Time (m:ss.s)':>13}  {'Cookies produced':>18}"
    )
    divider = (
        f"{'-' * 3}  {'-' * item_width}  "
        f"{'-' * 13}  {'-' * 18}"
    )
    return header, divider


def format_purchase_row(number, purchase, item_width):
    return (
        f"{number:>3}  {purchase.display_item:<{item_width}}  "
        f"{format_time(purchase.age):>13}  {purchase.cookies:>18,.1f}"
    )


def format_purchase_table(purchases, block_size=10):
    if not purchases:
        return ""

    item_width = max(
        len("Item"),
        *(len(purchase.display_item) for purchase in purchases),
    )
    header, divider = purchase_table_header(item_width)
    lines = []

    for first in range(0, len(purchases), block_size):
        if lines:
            lines.append("")
        lines.extend((header, divider))
        for number, purchase in enumerate(
            purchases[first : first + block_size], first + 1
        ):
            lines.append(format_purchase_row(number, purchase, item_width))

    return "\n".join(lines)


def live_item_width(game):
    items = ["Item", *game.upgrade_info]
    items.extend(
        f"Sell {name} #{LIVE_BUILDING_NUMBER}" for name in game.building_info
    )
    return max(map(len, items))


class LivePurchaseTable:
    def __init__(self, item_width, block_size=10):
        self.item_width = item_width
        self.block_size = block_size
        self.count = 0

    def print_purchase(self, purchase):
        if self.count % self.block_size == 0:
            if self.count:
                print()
            print(*purchase_table_header(self.item_width), sep="\n")
        self.count += 1
        print(
            format_purchase_row(self.count, purchase, self.item_width),
            flush=True,
        )


def print_result(result, target, include_table=True):
    game = result.game
    print(f"Target: {target:,} cookies")
    print(f"Time: {format_time(game.age)}")
    print(f"Final CpS: {game.cps():.3f}")
    print(f"Purchases: {len(result.purchases)}")
    if include_table and result.purchases:
        print()
        print(format_purchase_table(result.purchases))
    print(f"\nFinal time: {format_time(game.age)}")


def local_route_path(destination):
    path = Path(destination)
    if path.suffix != ".route":
        raise ValueError("route destination must end in .route")
    if not path.is_absolute():
        path = REPOSITORY / path
    path = path.resolve()
    if not path.is_relative_to(LOCAL_ROUTE_DIRECTORY.resolve()):
        raise ValueError("route destination must be inside routes/local/")
    return path


def save_route(
    destination,
    settings,
    result,
    overwrite=False,
):
    path = Path(destination)
    if path.suffix != ".route":
        raise ValueError("route destination must end in .route")
    if path.exists() and not overwrite:
        raise FileExistsError(f"Route already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Generated by make_route.py.",
        f"name = {path.stem}",
        "source = this codebase",
        f"version = {settings['version']}",
        f"target = {settings['target']}",
        f"click_rate = {settings['click_rate']:g}",
        f"purchase_delay = {settings['purchase_delay']:g}",
        f"price_cutoff_multiplier = {settings['price_cutoff_multiplier']:g}",
        f"initial_state = {settings['initial_state']}",
        f"allow_upgrades = {str(settings['allow_upgrades']).lower()}",
        "",
        *(purchase.route_action() for purchase in result.purchases),
        "",
    ]
    path.write_text("\n".join(lines))
    return path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Route a fresh Cookie Clicker run")
    parser.add_argument(
        "--category",
        choices=available_categories(),
        help="load defaults from categories/NAME.conf",
    )
    parser.add_argument(
        "--version",
        choices=SUPPORTED_VERSIONS,
    )
    parser.add_argument("--target", type=int)
    parser.add_argument("--click-rate", type=float)
    parser.add_argument("--purchase-delay", type=float)
    parser.add_argument("--price-cutoff-multiplier", type=float)
    parser.add_argument(
        "--save",
        metavar="ROUTE_FILE",
        help="save to a .route file under routes/local/",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace an existing local route used with --save",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print purchases as the route is calculated",
    )
    initial_state = parser.add_mutually_exclusive_group()
    initial_state.add_argument(
        "--initial-state",
        choices=("fresh", "neverclick"),
    )
    initial_state.add_argument(
        "--neverclick-start",
        dest="initial_state",
        action="store_const",
        const="neverclick",
        help="start after 15 handmade cookies and the first Cursor, with no clicking",
    )
    initial_state.add_argument(
        "--fresh-start",
        dest="initial_state",
        action="store_const",
        const="fresh",
        help="override a category's initial state with a fresh game",
    )
    upgrades = parser.add_mutually_exclusive_group()
    upgrades.add_argument(
        "--allow-upgrades",
        "--upgrades",
        dest="allow_upgrades",
        action="store_true",
        default=None,
        help="enable upgrade purchases",
    )
    upgrades.add_argument(
        "--no-upgrades",
        dest="allow_upgrades",
        action="store_false",
        help="disable upgrade purchases",
    )
    args = parser.parse_args(argv)

    settings = dict(DEFAULT_SETTINGS)
    if args.category:
        try:
            settings.update(load_category(args.category))
        except ValueError as error:
            parser.error(str(error))
    for key in DEFAULT_SETTINGS:
        cli_value = getattr(args, key)
        if cli_value is not None:
            settings[key] = cli_value

    if settings["target"] <= 0:
        parser.error("--target must be greater than zero")
    if settings["click_rate"] < 0:
        parser.error("--click-rate cannot be negative")
    if settings["purchase_delay"] < 0:
        parser.error("--purchase-delay cannot be negative")
    if settings["price_cutoff_multiplier"] <= 0:
        parser.error("--price-cutoff-multiplier must be greater than zero")
    if args.overwrite and not args.save:
        parser.error("--overwrite requires --save")
    save_path = None
    if args.save:
        try:
            save_path = local_route_path(args.save)
        except ValueError as error:
            parser.error(str(error))
        if save_path.exists() and not args.overwrite:
            parser.error(f"route already exists: {save_path}")

    game = Game(settings["version"])
    game.clickrate = settings["click_rate"]
    if settings["initial_state"] == "neverclick":
        game.initialize_neverclick()
        # Neverclick normally disables clicking, but an explicit CLI click rate
        # still wins over the category or initial-state behavior.
        if args.click_rate is not None:
            game.clickrate = args.click_rate
    settings["click_rate"] = game.clickrate
    game.purchase_delay = settings["purchase_delay"]
    game.price_cutoff_multiplier = settings["price_cutoff_multiplier"]
    game.allow_upgrades = settings["allow_upgrades"]
    print(f"Calculating route to {settings['target']:,} cookies...", flush=True)
    live_table = LivePurchaseTable(live_item_width(game)) if args.verbose else None
    result = find_route(
        game,
        settings["target"],
        on_purchase=live_table.print_purchase if live_table else None,
    )
    if live_table and live_table.count:
        print()
    if args.save:
        saved_path = save_route(
            save_path,
            settings,
            result,
            overwrite=args.overwrite,
        )
        print(f"Saved route: {saved_path.relative_to(REPOSITORY)}")
    print_result(result, settings["target"], include_table=False)


if __name__ == "__main__":
    main()

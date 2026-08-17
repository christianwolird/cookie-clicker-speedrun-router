#!/usr/bin/env python3

"""Command-line entry point for generating routes."""

import argparse
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parent
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.algorithms import DEFAULT_ALGORITHM, available_algorithms, get_algorithm
from src.algorithms.errand_queueing import DEFAULT_QUEUE_POPS
from src.config import (
    DEFAULT_SETTINGS,
    available_categories,
    load_category,
    local_route_path,
    validate_settings,
)
from src.data import SUPPORTED_VERSIONS
from src.gamestate import (
    DEFAULT_ERRAND_DURATION,
    DEFAULT_PURCHASE_CLICK_RATE,
    Gamestate,
)
from src.presentation import LiveRouteTable, format_route
from src.routes import RoutePlan, action_errands, write_route


def grouped_errands_enabled(algorithm):
    return algorithm == "errand_queueing"


def calculate_route(
    algorithm_name,
    initial_gamestate,
    target,
    price_horizon_multiplier,
    on_errand=None,
    errand_queue_depth=DEFAULT_QUEUE_POPS,
):
    options = {
        "on_errand": on_errand,
        "price_horizon_multiplier": price_horizon_multiplier,
    }
    if grouped_errands_enabled(algorithm_name):
        options["queue_pops"] = errand_queue_depth
    return get_algorithm(algorithm_name)(
        initial_gamestate,
        target,
        **options,
    )


def _parser():
    parser = argparse.ArgumentParser(
        description="Generate a Cookie Clicker purchase route"
    )
    parser.add_argument("--category", choices=available_categories())
    parser.add_argument(
        "--algorithm",
        choices=available_algorithms(),
        help=f"routing algorithm (default: {DEFAULT_ALGORITHM})",
    )
    parser.add_argument("--version", choices=SUPPORTED_VERSIONS)
    parser.add_argument("--target", type=int)
    parser.add_argument("--click-rate", type=float)
    parser.add_argument(
        "--errand-duration",
        type=float,
        help=f"fixed travel time per errand (default: {DEFAULT_ERRAND_DURATION:g})",
    )
    parser.add_argument(
        "--purchase-click-rate",
        type=float,
        help=(
            "distinct purchase types handled per second "
            f"(default: {DEFAULT_PURCHASE_CLICK_RATE:g})"
        ),
    )
    parser.add_argument(
        "--errand-queue-depth",
        type=int,
        help=(
            "maximum priority-queue pops per gamestate "
            f"(default: {DEFAULT_QUEUE_POPS})"
        ),
    )
    parser.add_argument(
        "--price-horizon-multiplier",
        type=float,
        help="maximum errand price as a multiple of lifetime cookies",
    )
    parser.add_argument(
        "--initial-state",
        choices=("fresh", "neverclick"),
    )
    upgrades = parser.add_mutually_exclusive_group()
    upgrades.add_argument(
        "--allow-upgrades",
        dest="upgrades_enabled",
        action="store_true",
        default=None,
    )
    upgrades.add_argument(
        "--no-upgrades",
        dest="upgrades_enabled",
        action="store_false",
    )
    parser.add_argument(
        "--save",
        metavar="ROUTE_FILE",
        help="save under routes/local/",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace the route passed to --save",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print each errand as it is selected",
    )
    return parser


def _resolve_settings(args):
    settings = dict(DEFAULT_SETTINGS)
    if args.category:
        settings.update(load_category(args.category))

    cli_overrides = set()
    for key in DEFAULT_SETTINGS:
        value = getattr(args, key)
        if value is not None:
            settings[key] = value
            cli_overrides.add(key)
    validate_settings(settings)
    return settings, cli_overrides


def _initial_gamestate(settings, cli_overrides):
    gamestate = Gamestate(settings["version"])
    if settings["initial_state"] == "neverclick":
        gamestate.initialize_neverclick()
        if "click_rate" in cli_overrides:
            gamestate.click_rate = settings["click_rate"]
    else:
        gamestate.click_rate = settings["click_rate"]
    gamestate.errand_duration = settings["errand_duration"]
    gamestate.purchase_click_rate = settings["purchase_click_rate"]
    gamestate.upgrades_allowed = settings["upgrades_enabled"]
    settings["click_rate"] = gamestate.click_rate
    return gamestate


def _setting(label, value, key, cli_overrides):
    suffix = "" if key in cli_overrides else " (default)"
    return f"{label}: {value}{suffix}"


def _print_settings(settings, cli_overrides):
    grouped = grouped_errands_enabled(settings["algorithm"])
    lines = [
        _setting("Algorithm", settings["algorithm"], "algorithm", cli_overrides),
        _setting(
            "Click rate",
            float(settings["click_rate"]),
            "click_rate",
            cli_overrides,
        ),
        _setting(
            "Errand travel delay",
            float(settings["errand_duration"]),
            "errand_duration",
            cli_overrides,
        ),
        _setting(
            "Purchase click rate",
            float(settings["purchase_click_rate"]),
            "purchase_click_rate",
            cli_overrides,
        ),
        _setting(
            "Upgrades enabled",
            settings["upgrades_enabled"],
            "upgrades_enabled",
            cli_overrides,
        ),
        _setting("Errands enabled", grouped, "algorithm", cli_overrides),
    ]
    if grouped:
        lines.append(
            _setting(
                "Errand queue depth",
                settings["errand_queue_depth"],
                "errand_queue_depth",
                cli_overrides,
            )
        )
    print(*lines, sep="\n")


def _save_result(path, settings, result, overwrite=False):
    grouped = grouped_errands_enabled(settings["algorithm"])
    plan = RoutePlan(
        name=path.stem,
        source="this codebase",
        version=settings["version"],
        target=settings["target"],
        click_rate=settings["click_rate"],
        initial_state=settings["initial_state"],
        algorithm=settings["algorithm"],
        errand_duration=settings["errand_duration"],
        purchase_click_rate=settings["purchase_click_rate"],
        upgrades_enabled=settings["upgrades_enabled"],
        errands_enabled=grouped,
        errands=action_errands(result),
        errand_queue_depth=(settings["errand_queue_depth"] if grouped else None),
    )
    return write_route(
        path,
        plan,
        comment="Generated by make_route.py.",
        overwrite=overwrite,
    )


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.overwrite and not args.save:
        parser.error("--overwrite requires --save")

    try:
        settings, cli_overrides = _resolve_settings(args)
        save_path = local_route_path(args.save) if args.save else None
        if save_path and save_path.exists() and not args.overwrite:
            raise FileExistsError(f"Route already exists: {save_path}")
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))

    gamestate = _initial_gamestate(settings, cli_overrides)
    _print_settings(settings, cli_overrides)
    print(f"\nCalculating route to {settings['target']:,} cookies...", flush=True)

    table = LiveRouteTable() if args.verbose else None
    result = calculate_route(
        settings["algorithm"],
        gamestate,
        settings["target"],
        settings["price_horizon_multiplier"],
        on_errand=table.print_errand if table else None,
        errand_queue_depth=settings["errand_queue_depth"],
    )
    if save_path:
        _save_result(save_path, settings, result, overwrite=args.overwrite)

    if table:
        table.print_done(result.final_gamestate, settings["target"])
    else:
        print(format_route(result, settings["target"], include_purchases=False))
    if save_path:
        print(f"Saved route: {save_path.relative_to(REPOSITORY)}")


if __name__ == "__main__":
    main()

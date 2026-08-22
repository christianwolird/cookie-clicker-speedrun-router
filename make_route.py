#!/usr/bin/env python3

"""Command-line entry point for generating routes."""

import argparse
import sys
from collections import Counter
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parent
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.algorithms import DEFAULT_ALGORITHM, available_algorithms, get_algorithm
from src.algorithms.errand_queueing import DEFAULT_FEELERS, DEFAULT_QUEUE_POPS
from src.algorithms.fuzzy_astar import (
    DEFAULT_FUZZY_SCALE,
    DEFAULT_MAX_EXPANSIONS,
    DEFAULT_PROGRESS_INTERVAL,
)
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
from src.presentation import LiveRouteTable, format_route, format_time
from src.routes import RoutePlan, action_errands, write_route


def grouped_errands_enabled(algorithm):
    return algorithm in {"errand_queueing", "fuzzy_astar"}


def calculate_route(
    algorithm_name,
    initial_gamestate,
    target,
    price_horizon_multiplier,
    on_errand=None,
    errand_queue_depth=DEFAULT_QUEUE_POPS,
    astar_feelers=DEFAULT_FEELERS,
    astar_fuzzy_scale=DEFAULT_FUZZY_SCALE,
    astar_max_expansions=DEFAULT_MAX_EXPANSIONS,
    on_progress=None,
    astar_progress_interval=DEFAULT_PROGRESS_INTERVAL,
):
    options = {
        "on_errand": on_errand,
        "price_horizon_multiplier": price_horizon_multiplier,
    }
    if grouped_errands_enabled(algorithm_name):
        options["queue_pops"] = errand_queue_depth
    if algorithm_name == "fuzzy_astar":
        options.update(
            feelers=astar_feelers,
            fuzzy_scale=astar_fuzzy_scale,
            max_expansions=astar_max_expansions,
            on_progress=on_progress,
            progress_interval=astar_progress_interval,
        )
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
        "--astar-feelers",
        type=int,
        help=f"outgoing errands per inventory (default: {DEFAULT_FEELERS})",
    )
    parser.add_argument(
        "--astar-fuzzy-scale",
        type=float,
        help=(
            "multiplier for fuzzy remaining time "
            f"(default: {DEFAULT_FUZZY_SCALE:g})"
        ),
    )
    parser.add_argument(
        "--astar-max-expansions",
        type=int,
        help=(
            "maximum non-stale inventories expanded "
            f"(default: {DEFAULT_MAX_EXPANSIONS:,})"
        ),
    )
    parser.add_argument(
        "--astar-progress-interval",
        type=float,
        default=DEFAULT_PROGRESS_INTERVAL,
        help=(
            "seconds between fuzzy-A* progress updates "
            f"(default: {DEFAULT_PROGRESS_INTERVAL:g})"
        ),
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
    if settings["algorithm"] == "fuzzy_astar":
        lines.extend(
            [
                _setting(
                    "A* feelers",
                    settings["astar_feelers"],
                    "astar_feelers",
                    cli_overrides,
                ),
                _setting(
                    "A* fuzzy scale",
                    settings["astar_fuzzy_scale"],
                    "astar_fuzzy_scale",
                    cli_overrides,
                ),
                _setting(
                    "A* maximum expansions",
                    settings["astar_max_expansions"],
                    "astar_max_expansions",
                    cli_overrides,
                ),
            ]
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
        astar_feelers=(
            settings["astar_feelers"]
            if settings["algorithm"] == "fuzzy_astar"
            else None
        ),
        astar_fuzzy_scale=(
            settings["astar_fuzzy_scale"]
            if settings["algorithm"] == "fuzzy_astar"
            else None
        ),
        astar_max_expansions=(
            settings["astar_max_expansions"]
            if settings["algorithm"] == "fuzzy_astar"
            else None
        ),
    )
    return write_route(
        path,
        plan,
        comment="Generated by make_route.py.",
        overwrite=overwrite,
    )


def _format_incoming_errand(errand):
    if not errand:
        return "start"
    counts = Counter((purchase.operation, purchase.item) for purchase in errand)
    parts = []
    for (operation, item), quantity in counts.items():
        label = f"{operation} {item}"
        if quantity > 1:
            label += f"×{quantity}"
        parts.append(label)
    if len(parts) > 3:
        parts = [*parts[:3], f"+{len(parts) - 3} types"]
    return " + ".join(parts)


def _print_astar_progress(progress):
    print(
        f"Search progress {format_time(progress.elapsed_seconds)}: "
        f"{progress.expanded:,} expanded, "
        f"{progress.generated:,} feelers, "
        f"{progress.relaxed:,} relaxed, "
        f"{progress.stale_skipped:,} stale, "
        f"{progress.queue_size:,} queued",
        flush=True,
    )
    frontier_estimate = (
        format_time(progress.frontier[0].estimated_finish)
        if progress.frontier
        else "none"
    )
    print(
        f"  Best finish {format_time(progress.best_finish_age)}; "
        f"top estimate {frontier_estimate}; "
        f"max queue {progress.maximum_queue_size:,}",
        flush=True,
    )
    print("  Frontier:", flush=True)
    for index, candidate in enumerate(progress.frontier, 1):
        print(
            "    "
            f"#{index} f={format_time(candidate.estimated_finish)} "
            f"age={format_time(candidate.age)} "
            f"life={candidate.lifetime_cookies:,.0f} "
            f"CpS={candidate.cps:,.1f} "
            f"via {_format_incoming_errand(candidate.incoming_errand)}",
            flush=True,
        )
    if not progress.frontier:
        print("    empty", flush=True)
    print(flush=True)


def main(argv=None):
    parser = _parser()
    args = parser.parse_args(argv)
    if args.overwrite and not args.save:
        parser.error("--overwrite requires --save")
    if args.astar_progress_interval <= 0:
        parser.error("--astar-progress-interval must be greater than zero")

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
        astar_feelers=settings["astar_feelers"],
        astar_fuzzy_scale=settings["astar_fuzzy_scale"],
        astar_max_expansions=settings["astar_max_expansions"],
        on_progress=(
            _print_astar_progress
            if settings["algorithm"] == "fuzzy_astar"
            else None
        ),
        astar_progress_interval=args.astar_progress_interval,
    )
    if save_path:
        _save_result(save_path, settings, result, overwrite=args.overwrite)

    if table:
        table.print_done(result.final_gamestate, settings["target"])
    else:
        print(format_route(result, settings["target"], include_purchases=False))
    stats = getattr(result, "search_stats", None)
    if stats is not None:
        print(
            "Search: "
            f"{stats.expanded:,} expanded, "
            f"{stats.generated:,} feelers, "
            f"{stats.relaxed:,} relaxed, "
            f"{stats.stale_skipped:,} stale, "
            f"{stats.heuristic_evaluations:,} heuristics, "
            f"{stats.fuzzy_route_evaluations:,} fuzzy routes, "
            f"{stats.checkpoint_tails:,} shared tails, "
            f"max queue {stats.maximum_queue_size:,}, "
            f"runtime {stats.elapsed_seconds:,.1f}s, "
            f"stopped by {stats.termination}"
        )
    if save_path:
        print(f"Saved route: {save_path.relative_to(REPOSITORY)}")


if __name__ == "__main__":
    main()

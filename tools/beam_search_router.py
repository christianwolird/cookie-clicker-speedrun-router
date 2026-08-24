#!/usr/bin/env python3

"""Generate a route with Beam search and a route-based Ruler heuristic."""

import argparse
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ccsr.config import (
    available_categories,
    available_player_profiles,
    create_initial_gamestate,
    load_category,
    load_player_profile,
)
from ccsr.errands.generator import DEFAULT_BEAM_WIDTH
from ccsr.presentation import LiveRouteTable, format_route, format_time
from ccsr.routes import (
    RoutePlan,
    action_errands,
    execute_route,
    load_route,
    write_route,
)
from ccsr.routing_algorithms.beam_search_router import (
    DEFAULT_MAX_EXPANSIONS,
    DEFAULT_PROGRESS_INTERVAL,
    find_route,
)
from ccsr.routing_algorithms.route_ruler import DEFAULT_RULER_SCALE


DEFAULT_PRICE_HORIZON_MULTIPLIER = 2.0
OUTPUT_DIRECTORY = REPOSITORY / "routes" / "generated" / "beam_routes"


def _save_path(destination):
    path = Path(destination)
    if path.suffix != ".route":
        raise ValueError("Route destination must end in .route")
    if not path.is_absolute():
        path = OUTPUT_DIRECTORY / path
    path = path.resolve()
    if not path.is_relative_to(OUTPUT_DIRECTORY.resolve()):
        raise ValueError(f"Route destination must be inside {OUTPUT_DIRECTORY}")
    return path


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


def _format_progress_time(seconds):
    minutes, remaining_seconds = divmod(round(seconds), 60)
    return f"{minutes}:{remaining_seconds:02d}"


def _print_progress(progress):
    print(
        f"Progress ({_format_progress_time(progress.elapsed_seconds)}) "
        f"{progress.expanded:,} expanded, "
        f"{progress.generated:,} neighbors, "
        f"{progress.relaxed:,} relaxed, "
        f"{progress.stale_skipped:,} stale, "
        f"{progress.queue_size:,} queued",
        flush=True,
    )
    print(
        f"  Best finish {format_time(progress.best_finish_age)}; "
        f"max queue {progress.maximum_queue_size:,}",
        flush=True,
    )
    for index, candidate in enumerate(progress.frontier, 1):
        print(
            f"  #{index} f={format_time(candidate.estimated_finish)} "
            f"age={format_time(candidate.age)} "
            f"life={candidate.lifetime_cookies:,.0f} "
            f"CpS={candidate.cps:,.1f} "
            f"via {_format_incoming_errand(candidate.incoming_errand)}",
            flush=True,
        )


def _load_ruler(path, category, player, for_quickster):
    plan = load_route(path)
    if plan.version != category.version:
        raise ValueError("Ruler route uses a different game version")
    if plan.for_quickster != for_quickster:
        raise ValueError(
            "Ruler route and Beam search must use the same Quickster mode"
        )
    plan = replace(
        plan,
        category=category.name,
        player_profile=player.name,
        target=category.target,
        click_rate=player.click_rate if category.clicking_enabled else 0.0,
        initial_state=category.initial_state,
        upgrades_enabled=category.upgrades_enabled,
        errand_delay=player.errand_delay,
        item_delay=player.item_delay,
    )
    return execute_route(plan, player=player, for_quickster=for_quickster)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--category",
        choices=available_categories(),
        default="one_million",
    )
    parser.add_argument(
        "--player",
        choices=available_player_profiles(),
        default="default_10_cps",
    )
    parser.add_argument(
        "--quickster",
        action="store_true",
        help="offer only single-item errands and apply zero purchase delay",
    )
    parser.add_argument(
        "--price-horizon-multiplier",
        type=float,
        default=DEFAULT_PRICE_HORIZON_MULTIPLIER,
    )
    parser.add_argument("--beam-width", type=int, default=DEFAULT_BEAM_WIDTH)
    parser.add_argument("--ruler-route", type=Path)
    parser.add_argument(
        "--ruler-scale",
        type=float,
        default=DEFAULT_RULER_SCALE,
    )
    parser.add_argument(
        "--max-expansions",
        type=int,
        default=DEFAULT_MAX_EXPANSIONS,
    )
    parser.add_argument(
        "--progress-interval",
        type=float,
        default=DEFAULT_PROGRESS_INTERVAL,
    )
    parser.add_argument("--save", metavar="NAME.route")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    positive = {
        "--price-horizon-multiplier": args.price_horizon_multiplier,
        "--beam-width": args.beam_width,
        "--max-expansions": args.max_expansions,
        "--progress-interval": args.progress_interval,
    }
    for option, value in positive.items():
        if value <= 0:
            parser.error(f"{option} must be greater than zero")
    if args.ruler_scale < 0:
        parser.error("--ruler-scale cannot be negative")
    if args.overwrite and not args.save:
        parser.error("--overwrite requires --save")

    try:
        category = load_category(args.category)
        player = load_player_profile(args.player)
        destination = _save_path(args.save) if args.save else None
        if destination and destination.exists() and not args.overwrite:
            raise FileExistsError(f"Route already exists: {destination}")
        ruler_route = (
            _load_ruler(
                args.ruler_route,
                category,
                player,
                args.quickster,
            )
            if args.ruler_route
            else None
        )
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))

    gamestate = create_initial_gamestate(
        category,
        player,
        for_quickster=args.quickster,
    )
    print(f"Category: {category.name}")
    print(f"Player: {player.name}")
    print(f"For Quickster: {args.quickster}")
    print(f"Beam width: {args.beam_width}")
    print(f"Ruler route: {args.ruler_route or 'temporary greedy route'}")
    print(f"Ruler scale: {args.ruler_scale:g}")
    print(f"\nCalculating route to {category.target:,} cookies...", flush=True)

    table = LiveRouteTable() if args.verbose else None
    result = find_route(
        gamestate,
        category.target,
        on_errand=table.print_errand if table else None,
        price_horizon_multiplier=args.price_horizon_multiplier,
        beam_width=args.beam_width,
        ruler_route=ruler_route,
        ruler_scale=args.ruler_scale,
        max_expansions=args.max_expansions,
        on_progress=_print_progress,
        progress_interval=args.progress_interval,
        for_quickster=args.quickster,
    )
    if table:
        table.print_done(result.final_gamestate, category.target)
    else:
        print(format_route(result, category.target, include_purchases=False))
    stats = result.search_stats
    print(
        "Search: "
        f"{stats.expanded:,} expanded, "
        f"{stats.generated:,} neighbors, "
        f"{stats.relaxed:,} relaxed, "
        f"{stats.stale_skipped:,} stale, "
        f"{stats.heuristic_evaluations:,} estimates, "
        f"max queue {stats.maximum_queue_size:,}, "
        f"runtime {stats.elapsed_seconds:,.1f}s, "
        f"stopped by {stats.termination}"
    )

    if destination:
        plan = RoutePlan(
            name=destination.stem,
            source="this codebase",
            category=category.name,
            player_profile=player.name,
            version=category.version,
            target=category.target,
            click_rate=gamestate.click_rate,
            initial_state=category.initial_state,
            algorithm="beam_search_router",
            upgrades_enabled=category.upgrades_enabled,
            for_quickster=args.quickster,
            errands=action_errands(result),
            errand_delay=player.errand_delay,
            item_delay=player.item_delay,
            price_horizon_multiplier=args.price_horizon_multiplier,
            beam_width=args.beam_width,
            ruler_scale=args.ruler_scale,
            ruler_route=str(args.ruler_route or "generated_greedy"),
            beam_max_expansions=args.max_expansions,
        )
        write_route(
            destination,
            plan,
            comment="Generated by tools/beam_search_router.py.",
            explicit_errands=not args.quickster,
            overwrite=args.overwrite,
        )
        print(f"Saved route: {destination.relative_to(REPOSITORY)}")


if __name__ == "__main__":
    main()

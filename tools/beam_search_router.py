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
    available_route_profiles,
    available_player_profiles,
    create_initial_gamestate,
    load_route_profile,
    load_player_profile,
    available_errand_profiles,
    load_errand_profile,
)
from ccsr.game.data import SUPPORTED_VERSIONS
from ccsr.routes.layout import generated_route_path
from ccsr.errands.generator import (
    DEFAULT_BEAM_WIDTH, DEFAULT_QUEUE_EXPANSIONS, DEFAULT_MAX_ERRAND_ACTIONS,
)
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
OUTPUT_DIRECTORY = REPOSITORY / "routes"


def _save_path(destination, route_type):
    return generated_route_path(destination, route_type, "generated_beam", OUTPUT_DIRECTORY)

def _format_incoming_errand(errand):
    if not errand:
        return "start"
    counts = Counter()
    for purchase in errand:
        counts[purchase.operation, purchase.item] += purchase.quantity
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


def _load_ruler(path, route_profile, player, for_quickster, errand_profile):
    plan = load_route(path)
    if plan.version != route_profile.version:
        raise ValueError("Ruler route uses a different game version")
    if plan.for_quickster != for_quickster:
        raise ValueError(
            "Ruler route and Beam search must use the same Quickster mode"
        )
    if plan.bulk_size != errand_profile.bulk_size:
        raise ValueError("Ruler route uses a different fixed bulk size")
    plan = replace(
        plan,
        goal=route_profile.goal,
        route_profile=route_profile.name,
        achievement_curve=route_profile.achievement_curve,
        player_profile=player.name,
        target=route_profile.target,
        click_rate=player.click_rate,
        initial_state=player.initial_state,
        upgrades_enabled=route_profile.upgrades_enabled,
        errand_delay=player.errand_delay,
        action_delay=player.action_delay,
    )
    return execute_route(
        plan, player=player, for_quickster=for_quickster, errand_profile=errand_profile,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--route-profile",
        choices=available_route_profiles(),
        default="million-25cps",
    )
    parser.add_argument("--version", choices=SUPPORTED_VERSIONS, help="override the route profile game version")
    parser.add_argument(
        "--player",
        choices=available_player_profiles(),
    )
    parser.add_argument(
        "--quickster",
        action="store_true",
        help="offer only single-click errands and apply zero action delay",
    )
    parser.add_argument("--errand-profile", choices=available_errand_profiles())
    parser.add_argument("--max-errand-actions", type=int, default=DEFAULT_MAX_ERRAND_ACTIONS)
    parser.add_argument(
        "--errand-search-width", type=int,
        help="inner queue width (defaults to --beam-width)",
    )
    parser.add_argument("--errand-queue-expansions", type=int, default=DEFAULT_QUEUE_EXPANSIONS)
    parser.add_argument(
        "--price-horizon-multiplier",
        type=float,
        default=DEFAULT_PRICE_HORIZON_MULTIPLIER,
    )
    parser.add_argument("--beam-width", type=int, default=DEFAULT_BEAM_WIDTH)
    parser.add_argument("--workers", type=int, default=1,
                        help="processes for speculative errand generation; preserves serial search order")
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
    parser.add_argument("--save", nargs="?", const="generated_beam.route", metavar="NAME.route")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    positive = {
        "--price-horizon-multiplier": args.price_horizon_multiplier,
        "--beam-width": args.beam_width,
        "--workers": args.workers,
        "--max-expansions": args.max_expansions,
        "--progress-interval": args.progress_interval,
        "--max-errand-actions": args.max_errand_actions,
        "--errand-search-width": args.errand_search_width or args.beam_width,
        "--errand-queue-expansions": args.errand_queue_expansions,
    }
    for option, value in positive.items():
        if value <= 0:
            parser.error(f"{option} must be greater than zero")
    if args.errand_search_width == 0:
        parser.error("--errand-search-width must be greater than zero")
    if args.ruler_scale < 0:
        parser.error("--ruler-scale cannot be negative")
    if args.overwrite and not args.save:
        parser.error("--overwrite requires --save")

    try:
        route_profile = load_route_profile(args.route_profile)
        route_profile = replace(route_profile, version=args.version or route_profile.version)
        player = load_player_profile(args.player or route_profile.player_profile)
        errand_profile = load_errand_profile(args.errand_profile or route_profile.errand_profile)
        destination = _save_path(args.save, args.route_profile) if args.save else None
        if destination and destination.exists() and not args.overwrite:
            raise FileExistsError(f"Route already exists: {destination}")
        ruler_route = (
            _load_ruler(
                args.ruler_route,
                route_profile,
                player,
                args.quickster,
                errand_profile,
            )
            if args.ruler_route
            else None
        )
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))

    gamestate = create_initial_gamestate(
        route_profile,
        player,
        for_quickster=args.quickster,
        errand_profile=errand_profile,
    )
    print(f"Route profile: {route_profile.name}")
    print(f"Goal: {route_profile.goal}")
    print(f"Game version: {route_profile.version}")
    print(f"Player: {player.name}")
    print(f"Errand profile: {errand_profile.name} (x{errand_profile.bulk_size})")
    print(f"For Quickster: {args.quickster}")
    print(f"Beam width: {args.beam_width}")
    print(f"Workers: {args.workers}")
    print(f"Ruler route: {args.ruler_route or 'temporary greedy route'}")
    print(f"Ruler scale: {args.ruler_scale:g}")
    print(f"\nCalculating route to {route_profile.target:,} cookies...", flush=True)

    table = LiveRouteTable(gamestate.lifetime_cookies) if args.verbose else None
    result = find_route(
        gamestate,
        route_profile.target,
        on_errand=table.print_errand if table else None,
        price_horizon_multiplier=args.price_horizon_multiplier,
        beam_width=args.beam_width,
        ruler_route=ruler_route,
        ruler_scale=args.ruler_scale,
        max_expansions=args.max_expansions,
        on_progress=_print_progress,
        progress_interval=args.progress_interval,
        for_quickster=args.quickster,
        errand_search_width=args.errand_search_width,
        errand_queue_expansions=args.errand_queue_expansions,
        max_errand_actions=args.max_errand_actions,
        workers=args.workers,
    )
    if table:
        table.print_done(result.final_gamestate, route_profile.target)
    else:
        print(format_route(result, route_profile.target, include_purchases=False))
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
            goal=route_profile.goal,
            route_profile=route_profile.name,
            achievement_curve=route_profile.achievement_curve,
            player_profile=player.name,
            version=route_profile.version,
            target=route_profile.target,
            click_rate=gamestate.click_rate,
            initial_state=player.initial_state,
            algorithm="beam_search_router",
            upgrades_enabled=route_profile.upgrades_enabled,
            for_quickster=args.quickster,
            errands=action_errands(result),
            errand_delay=player.errand_delay,
            action_delay=player.action_delay,
            errand_profile=errand_profile.name,
            bulk_size=errand_profile.bulk_size,
            selling_allowed=errand_profile.selling_allowed,
            errand_search_width=args.errand_search_width or args.beam_width,
            errand_queue_depth=args.errand_queue_expansions,
            max_errand_actions=args.max_errand_actions,
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

#!/usr/bin/env python3

"""Generate a route by repeatedly selecting the best scored errand."""

import argparse
import sys
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
    available_errand_profiles,
    load_errand_profile,
)
from ccsr.errands.generator import DEFAULT_QUEUE_EXPANSIONS, DEFAULT_MAX_ERRAND_ACTIONS
from ccsr.presentation import LiveRouteTable, format_route
from ccsr.routes import RoutePlan, action_errands, write_route
from ccsr.routing_algorithms.greedy_router import find_route


DEFAULT_PRICE_HORIZON_MULTIPLIER = 2.0
OUTPUT_DIRECTORY = REPOSITORY / "routes" / "generated" / "greedy_routes"


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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--category",
        choices=available_categories(),
        default="one_million_v2",
    )
    parser.add_argument(
        "--player",
        choices=available_player_profiles(),
        default="default_10_cps",
    )
    parser.add_argument(
        "--quickster",
        action="store_true",
        help="offer only single-click errands and apply zero action delay",
    )
    parser.add_argument("--errand-profile", choices=available_errand_profiles(), default="single")
    parser.add_argument("--max-errand-actions", type=int, default=DEFAULT_MAX_ERRAND_ACTIONS)
    parser.add_argument(
        "--price-horizon-multiplier",
        type=float,
        default=DEFAULT_PRICE_HORIZON_MULTIPLIER,
    )
    parser.add_argument(
        "--queue-expansions",
        type=int,
        default=DEFAULT_QUEUE_EXPANSIONS,
        help="maximum priority-queue expansions per gamestate",
    )
    parser.add_argument("--save", metavar="NAME.route")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    if args.price_horizon_multiplier <= 0:
        parser.error("--price-horizon-multiplier must be greater than zero")
    if args.queue_expansions <= 0:
        parser.error("--queue-expansions must be greater than zero")
    if args.max_errand_actions <= 0:
        parser.error("--max-errand-actions must be greater than zero")
    if args.overwrite and not args.save:
        parser.error("--overwrite requires --save")

    try:
        category = load_category(args.category)
        player = load_player_profile(args.player)
        errand_profile = load_errand_profile(args.errand_profile)
        destination = _save_path(args.save) if args.save else None
        if destination and destination.exists() and not args.overwrite:
            raise FileExistsError(f"Route already exists: {destination}")
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))

    gamestate = create_initial_gamestate(
        category,
        player,
        for_quickster=args.quickster,
        errand_profile=errand_profile,
    )
    print(f"Category: {category.name}")
    print(f"Player: {player.name}")
    print(f"Errand profile: {errand_profile.name} (x{errand_profile.bulk_size})")
    print(f"For Quickster: {args.quickster}")
    print(f"Click rate: {gamestate.click_rate:g}")
    if not args.quickster:
        print(f"Errand delay: {gamestate.errand_delay:g}")
        print(f"Action delay: {gamestate.action_delay:g}")
    print(f"Queue expansions: {args.queue_expansions}")
    print(f"\nCalculating route to {category.target:,} cookies...", flush=True)

    table = LiveRouteTable(gamestate.lifetime_cookies) if args.verbose else None
    result = find_route(
        gamestate,
        category.target,
        on_errand=table.print_errand if table else None,
        price_horizon_multiplier=args.price_horizon_multiplier,
        queue_expansions=args.queue_expansions,
        for_quickster=args.quickster,
        max_errand_actions=args.max_errand_actions,
    )
    if table:
        table.print_done(result.final_gamestate, category.target)
    else:
        print(format_route(result, category.target, include_purchases=False))

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
            algorithm="greedy_router",
            upgrades_enabled=category.upgrades_enabled,
            for_quickster=args.quickster,
            errands=action_errands(result),
            errand_delay=player.errand_delay,
            action_delay=player.action_delay,
            errand_profile=errand_profile.name,
            bulk_size=errand_profile.bulk_size,
            selling_allowed=errand_profile.selling_allowed,
            max_errand_actions=args.max_errand_actions,
            price_horizon_multiplier=args.price_horizon_multiplier,
            errand_queue_depth=args.queue_expansions,
        )
        write_route(
            destination,
            plan,
            comment="Generated by tools/greedy_router.py.",
            explicit_errands=not args.quickster,
            overwrite=args.overwrite,
        )
        print(f"Saved route: {destination.relative_to(REPOSITORY)}")


if __name__ == "__main__":
    main()

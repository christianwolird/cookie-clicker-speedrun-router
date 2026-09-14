#!/usr/bin/env python3

"""Generate a route by repeatedly selecting the best scored errand."""

import argparse
import sys
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
from ccsr.errands.generator import DEFAULT_QUEUE_EXPANSIONS, DEFAULT_MAX_ERRAND_ACTIONS
from ccsr.presentation import LiveRouteTable, format_route
from ccsr.routes import RoutePlan, action_errands, write_route
from ccsr.routing_algorithms.greedy_router import find_route


DEFAULT_PRICE_HORIZON_MULTIPLIER = 2.0
OUTPUT_DIRECTORY = REPOSITORY / "routes"


def _save_path(destination, route_type):
    return generated_route_path(destination, route_type, "generated_greedy", OUTPUT_DIRECTORY)

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
    parser.add_argument("--save", nargs="?", const="generated_greedy.route", metavar="NAME.route")
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
        route_profile = load_route_profile(args.route_profile)
        route_profile = replace(route_profile, version=args.version or route_profile.version)
        player = load_player_profile(args.player or route_profile.player_profile)
        errand_profile = load_errand_profile(args.errand_profile or route_profile.errand_profile)
        destination = _save_path(args.save, args.route_profile) if args.save else None
        if destination and destination.exists() and not args.overwrite:
            raise FileExistsError(f"Route already exists: {destination}")
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
    print(f"Click rate: {gamestate.click_rate:g}")
    if not args.quickster:
        print(f"Errand delay: {gamestate.errand_delay:g}")
        print(f"Action delay: {gamestate.action_delay:g}")
    print(f"Queue expansions: {args.queue_expansions}")
    print(f"\nCalculating route to {route_profile.target:,} cookies...", flush=True)

    table = LiveRouteTable(gamestate.lifetime_cookies) if args.verbose else None
    result = find_route(
        gamestate,
        route_profile.target,
        on_errand=table.print_errand if table else None,
        price_horizon_multiplier=args.price_horizon_multiplier,
        queue_expansions=args.queue_expansions,
        for_quickster=args.quickster,
        max_errand_actions=args.max_errand_actions,
    )
    if table:
        table.print_done(result.final_gamestate, route_profile.target)
    else:
        print(format_route(result, route_profile.target, include_purchases=False))

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
            algorithm="greedy_router",
            upgrades_enabled=route_profile.upgrades_enabled,
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

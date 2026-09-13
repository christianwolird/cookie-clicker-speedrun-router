#!/usr/bin/env python3

"""Replay a stored route with its recorded or an overridden player profile."""

import argparse
import sys
from pathlib import Path
from time import monotonic, sleep


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from ccsr.config import (
    available_player_profiles, load_player_profile,
    available_errand_profiles, load_errand_profile,
)
from ccsr.game.data import SUPPORTED_VERSIONS
from ccsr.presentation import LiveRouteTable, format_route
from ccsr.routes import execute_route, initial_gamestate, load_route


def _wait_until(started_at, age):
    remaining = started_at + age - monotonic()
    if remaining > 0:
        sleep(remaining)


def main(argv=None):
    started_at = monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route_file")
    parser.add_argument("--version", choices=SUPPORTED_VERSIONS)
    parser.add_argument("--player", choices=available_player_profiles())
    parser.add_argument(
        "--errand-profile", choices=available_errand_profiles(),
        help="override and validate the route's shop rules",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="print purchases and completion at their simulated times (implies --verbose)",
    )
    args = parser.parse_args(argv)

    try:
        plan = load_route(args.route_file)
        player = load_player_profile(args.player) if args.player else None
        errand_profile = (
            load_errand_profile(args.errand_profile) if args.errand_profile else None
        )
    except ValueError as error:
        parser.error(str(error))

    active_profile = player.name if player else plan.player_profile
    print(f"Replaying {plan.category} route for {active_profile}...", flush=True)
    print(f"Errand profile: {args.errand_profile or plan.errand_profile or 'legacy x1'}", flush=True)
    table = (
        LiveRouteTable(
            initial_gamestate(
                plan, player=player, version=args.version, errand_profile=errand_profile,
            ).lifetime_cookies
        )
        if args.verbose or args.realtime
        else None
    )

    def print_errand(errand):
        if args.realtime:
            # All purchases in an errand close at the same simulated time.
            _wait_until(started_at, errand[0].age)
        table.print_errand(errand)

    try:
        result = execute_route(
            plan,
            args.version,
            on_errand=print_errand if table else None,
            player=player,
            errand_profile=errand_profile,
        )
    except ValueError as error:
        parser.error(str(error))
    if table:
        if args.realtime:
            _wait_until(started_at, result.final_gamestate.age)
        table.print_done(result.final_gamestate, plan.target)
    else:
        print(format_route(result, plan.target, include_purchases=False))


if __name__ == "__main__":
    main()

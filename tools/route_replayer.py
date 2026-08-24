#!/usr/bin/env python3

"""Replay a stored route with its recorded or an overridden player profile."""

import argparse
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from ccsr.config import available_player_profiles, load_player_profile
from ccsr.game.data import SUPPORTED_VERSIONS
from ccsr.presentation import LiveRouteTable, format_route
from ccsr.routes import execute_route, load_route


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("route_file")
    parser.add_argument("--version", choices=SUPPORTED_VERSIONS)
    parser.add_argument("--player", choices=available_player_profiles())
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args(argv)

    try:
        plan = load_route(args.route_file)
        player = load_player_profile(args.player) if args.player else None
    except ValueError as error:
        parser.error(str(error))

    active_profile = player.name if player else plan.player_profile
    print(f"Replaying {plan.category} route for {active_profile}...", flush=True)
    table = LiveRouteTable() if args.verbose else None
    result = execute_route(
        plan,
        args.version,
        on_errand=table.print_errand if table else None,
        player=player,
    )
    if table:
        table.print_done(result.final_gamestate, plan.target)
    else:
        print(format_route(result, plan.target, include_purchases=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

"""Replay a stored route with the simulator."""

import argparse
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.data import SUPPORTED_VERSIONS
from src.presentation import LiveRouteTable, format_route
from src.routes import execute_route, load_route


def main(argv=None):
    parser = argparse.ArgumentParser(description="Replay a stored route")
    parser.add_argument("route_file")
    parser.add_argument("--version", choices=SUPPORTED_VERSIONS)
    parser.add_argument("--errand-duration", type=float)
    parser.add_argument("--purchase-click-rate", type=float)
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="print each errand as it is replayed",
    )
    args = parser.parse_args(argv)

    if args.errand_duration is not None and args.errand_duration < 0:
        parser.error("--errand-duration cannot be negative")
    if args.purchase_click_rate is not None and args.purchase_click_rate <= 0:
        parser.error("--purchase-click-rate must be greater than zero")

    try:
        plan = load_route(args.route_file)
    except ValueError as error:
        parser.error(str(error))

    table = LiveRouteTable() if args.verbose else None
    print(f"Replaying route to {plan.target:,} cookies...", flush=True)
    result = execute_route(
        plan,
        args.version,
        on_errand=table.print_errand if table else None,
        errand_duration=args.errand_duration,
        purchase_click_rate=args.purchase_click_rate,
    )
    if table:
        table.print_done(result.final_gamestate, plan.target)
    else:
        print(format_route(result, plan.target, include_purchases=False))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Browse named route profiles and saved routes without moving or rewriting files."""

import argparse
import json
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE = REPOSITORY / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ccsr.config import available_route_profiles
from ccsr.game.data import SUPPORTED_VERSIONS
from ccsr.presentation import format_time
from ccsr.routes.catalog import entry_details, inspect_route, profile_catalog, scan_routes
from ccsr.routes.layout import ROUTE_KINDS


def _table(headers, rows):
    rows = [tuple(str(value) for value in row) for row in rows]
    widths = [max(len(header), *(len(row[index]) for row in rows)) for index, header in enumerate(headers)]
    print("  ".join(header.ljust(width) for header, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths)))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("list", "profiles", "show"), nargs="?", default="list")
    parser.add_argument("route", nargs="?", type=Path, help="file to inspect with show")
    parser.add_argument("--root", type=Path, default=REPOSITORY / "routes")
    parser.add_argument("--goal")
    parser.add_argument("--version", choices=SUPPORTED_VERSIONS)
    parser.add_argument("--player", help="filter stored player profile names, including retired names")
    parser.add_argument("--errand-profile")
    parser.add_argument(
        "--route-type", "--route-profile", dest="route_profile", choices=available_route_profiles(),
        help="browse one route type, including its community and generated variants",
    )
    parser.add_argument("--matching-profile", choices=available_route_profiles(), help="match exact current human settings")
    parser.add_argument("--mode", choices=("quickster", "human"))
    parser.add_argument("--origin", choices=("community", "generated", "other"))
    parser.add_argument("--algorithm")
    parser.add_argument("--kind", choices=sorted(ROUTE_KINDS))
    parser.add_argument("--json", action="store_true", help="include complete resolved metadata as JSON")
    args = parser.parse_args(argv)
    if (args.command == "show") != (args.route is not None):
        parser.error("show requires a route file; other commands do not take a route file")
    try:
        profiles = profile_catalog()
        if args.command == "profiles":
            rows = [profile for profile in profiles if (
                (not args.route_profile or profile["name"] == args.route_profile)
                and (not args.goal or profile["goal"] == args.goal)
                and (not args.version or profile["version"] == args.version)
                and (not args.player or profile["player_profile"] == args.player)
                and (not args.errand_profile or profile["errand_profile"] == args.errand_profile)
            )]
            if args.json:
                print(json.dumps(rows, indent=2))
            elif rows:
                _table(
                    ("Profile", "Goal", "Version", "Player", "CPS", "Errands", "Upgrades"),
                    [(row["name"], row["goal"], row["version"], row["player_profile"],
                      f'{row["click_rate"]:g}', row["errand_profile"], row["upgrades_enabled"]) for row in rows],
                )
            else:
                print("No matching route profiles.")
            return
        if args.command == "show":
            path = args.route if args.route.is_file() else args.root / args.route
            entry = inspect_route(path)
            details = entry_details(entry, profiles=profiles)
            if args.json:
                print(json.dumps(details, indent=2))
            else:
                for key, value in details.items():
                    print(f"{key}: {value}")
            if entry.error:
                raise SystemExit(1)
            return
        entries = scan_routes(args.root)
        rows = []
        errors = []
        for entry in entries:
            row = entry_details(entry, profiles=profiles, root=args.root)
            if entry.error:
                errors.append({"path": row["path"], "error": entry.error})
            if entry.plan is None:
                continue
            filters = {
                "goal": args.goal, "version": args.version, "player_profile": args.player,
                "errand_profile": args.errand_profile, "execution": args.mode,
                "origin": args.origin, "algorithm": args.algorithm,
                "route_kind": args.kind,
            }
            if any(value is not None and row[key] != value for key, value in filters.items()):
                continue
            if args.route_profile and row["route_type"] != args.route_profile:
                continue
            if args.matching_profile and args.matching_profile not in row["matching_profiles"]:
                continue
            rows.append(row)
        rows.sort(key=lambda row: (
            row["route_type"], row["goal"], row["version"], row["player_profile"], row["execution"],
            row["errand_model"], row["errand_profile"] or "", row["path"],
        ))
        if args.json:
            print(json.dumps({"routes": rows, "errors": errors}, indent=2))
        elif rows:
            _table(
                ("Type", "Goal", "Version", "Player / CPS", "Errands", "Mode", "Algorithm", "Finish", "File"),
                [(row["route_type"], row["goal"], row["version"], f'{row["player_profile"]} / {row["click_rate"]:g}',
                  row["errand_profile"] or "legacy_x1", row["execution"], row["algorithm"],
                  format_time(row["finish_seconds"]) if row["finish_seconds"] is not None else "ERROR",
                  row["path"]) for row in rows],
            )
            print(f"\n{len(rows)} routes. Times use stored settings; Quickster and human times are separate.")
        else:
            print("No matching routes.")
        if errors:
            if not args.json:
                for error in errors:
                    print(f'{error["path"]}: {error["error"]}', file=sys.stderr)
            raise SystemExit(1)
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

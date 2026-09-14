#!/usr/bin/env python3

"""Group a Quickster route into human-executable errands."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
SOURCE_DIRECTORY = REPOSITORY / "src"
if str(SOURCE_DIRECTORY) not in sys.path:
    sys.path.insert(0, str(SOURCE_DIRECTORY))

from ccsr.config import (
    available_player_profiles, load_player_profile,
    available_errand_profiles, load_errand_profile,
    available_route_profiles, load_route_profile, PlayerProfile,
)
from ccsr.errands.errandifier import (
    DEFAULT_MAX_ERRAND_SIZE,
    DEFAULT_STATE_WIDTH,
    partition_contiguous_actions,
)
from ccsr.routes import initial_gamestate, load_route, write_route, use_route_profile


def errandify_plan(
    plan, player, max_errand_size=DEFAULT_MAX_ERRAND_SIZE, *,
    errand_profile=None, state_width=DEFAULT_STATE_WIDTH,
):
    if not plan.for_quickster or any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Input route must be a Quickster route")
    return partition_contiguous_actions(
        initial_gamestate(plan, player=player, for_quickster=False, errand_profile=errand_profile),
        plan.actions,
        max_errand_size,
        state_width=state_width,
    )


def save_errandified_route(
    destination,
    plan,
    player,
    errands,
    max_errand_size=DEFAULT_MAX_ERRAND_SIZE,
    *,
    overwrite=False,
    errand_profile=None,
    state_width=DEFAULT_STATE_WIDTH,
):
    errandified = replace(
        plan,
        player_profile=player.name,
        click_rate=player.click_rate,
        initial_state=player.initial_state,
        algorithm="errandifier",
        for_quickster=False,
        errands=errands,
        errand_delay=player.errand_delay,
        action_delay=player.action_delay,
        price_horizon_multiplier=None,
        errand_queue_depth=None,
        max_errand_size=max_errand_size,
        beam_width=None,
        ruler_scale=None,
        ruler_route=None,
        beam_max_expansions=None,
        errand_profile=errand_profile.name if errand_profile is not None else plan.errand_profile,
        bulk_size=errand_profile.bulk_size if errand_profile is not None else plan.bulk_size,
        selling_allowed=(
            errand_profile.selling_allowed if errand_profile is not None else plan.selling_allowed
        ),
        errand_search_width=None,
        max_errand_actions=None,
        errand_state_width=state_width if errand_profile is not None or plan.errand_profile else None,
    )
    return write_route(
        destination,
        errandified,
        comment="Grouped by tools/errandifier.py.",
        overwrite=overwrite,
    )


def _default_output(source):
    if source.is_dir():
        return source
    if source.name.startswith("community_quickster_"):
        return source.with_name(source.name.replace("community_quickster_", "community_errandified_", 1))
    return source.with_name(f"{source.stem}_errandified.route")


def _route_pairs(source, output):
    if source.is_dir():
        paths = sorted(source.rglob("community_quickster_*.route"))
        if not paths:
            paths = [path for path in sorted(source.glob("*.route")) if load_route(path).for_quickster]
        pairs = []
        for path in paths:
            if output == source:
                destination = _default_output(path)
            else:
                relative = path.relative_to(source)
                destination = output / relative.parent / _default_output(path).name
            pairs.append((path, destination))
        return tuple(pairs)
    if not source.is_file():
        raise ValueError(f"Input route does not exist: {source}")
    if output.exists() and output.is_dir():
        output = output / _default_output(source).name
    return ((source, output),)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--player", choices=available_player_profiles())
    parser.add_argument("--route-profile", choices=available_route_profiles())
    parser.add_argument(
        "--errand-profile", choices=available_errand_profiles(),
        help="compile under fixed shop rules; omitted preserves the source model",
    )
    parser.add_argument("--state-width", type=int, default=DEFAULT_STATE_WIDTH)
    parser.add_argument(
        "--max-errand-size",
        type=int,
        default=DEFAULT_MAX_ERRAND_SIZE,
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.max_errand_size <= 0:
        parser.error("--max-errand-size must be greater than zero")
    if args.state_width <= 0:
        parser.error("--state-width must be greater than zero")

    output = args.output or _default_output(args.source)
    try:
        errand_profile = load_errand_profile(args.errand_profile) if args.errand_profile else None
        pairs = _route_pairs(args.source, output)
        if args.route_profile and args.output is None:
            directory = REPOSITORY / "routes" / args.route_profile
            pairs = tuple((source, directory / destination.name) for source, destination in pairs)
        if len({destination for _, destination in pairs}) != len(pairs):
            raise ValueError("Multiple source routes would use the same destination filename")
        if not pairs:
            raise ValueError(f"No .route files found in {args.source}")
        if not args.overwrite:
            existing = [destination for _, destination in pairs if destination.exists()]
            if existing:
                raise FileExistsError(f"Route already exists: {existing[0]}")
        for source, destination in pairs:
            plan = load_route(source)
            if args.route_profile:
                plan = use_route_profile(plan, load_route_profile(args.route_profile))
            if args.player:
                player = load_player_profile(args.player)
            elif plan.player_profile in available_player_profiles():
                player = load_player_profile(plan.player_profile)
            else:
                # Historical profiles may have been retired. Their recorded
                # settings still suffice to process the route reproducibly.
                player = PlayerProfile(
                    plan.player_profile, plan.click_rate, plan.errand_delay,
                    plan.action_delay, plan.initial_state,
                )
            errands = errandify_plan(
                plan, player, args.max_errand_size,
                errand_profile=errand_profile, state_width=args.state_width,
            )
            saved = save_errandified_route(
                destination,
                plan,
                player,
                errands,
                args.max_errand_size,
                overwrite=args.overwrite,
                errand_profile=errand_profile,
                state_width=args.state_width,
            )
            print(saved)
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

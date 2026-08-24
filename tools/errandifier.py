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

from ccsr.config import available_player_profiles, load_player_profile
from ccsr.errands.errandifier import (
    DEFAULT_MAX_ERRAND_SIZE,
    partition_contiguous_actions,
)
from ccsr.routes import initial_gamestate, load_route, write_route


def errandify_plan(plan, player, max_errand_size=DEFAULT_MAX_ERRAND_SIZE):
    if not plan.for_quickster or any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Input route must be a Quickster route")
    return partition_contiguous_actions(
        initial_gamestate(plan, player=player, for_quickster=False),
        plan.actions,
        max_errand_size,
    )


def save_errandified_route(
    destination,
    plan,
    player,
    errands,
    max_errand_size=DEFAULT_MAX_ERRAND_SIZE,
    *,
    overwrite=False,
):
    errandified = replace(
        plan,
        player_profile=player.name,
        click_rate=(0.0 if plan.initial_state == "neverclick" else player.click_rate),
        algorithm="errandifier",
        for_quickster=False,
        errands=errands,
        errand_delay=player.errand_delay,
        item_delay=player.item_delay,
        price_horizon_multiplier=None,
        errand_queue_depth=None,
        max_errand_size=max_errand_size,
        beam_width=None,
        ruler_scale=None,
        ruler_route=None,
        beam_max_expansions=None,
    )
    return write_route(
        destination,
        errandified,
        comment="Grouped by tools/errandifier.py.",
        overwrite=overwrite,
    )


def _default_output(source):
    if source.is_dir():
        return source.parent / "erranded"
    if source.parent.name == "quickster_originals":
        return source.parent.parent / "erranded" / source.name
    return source.with_name(f"{source.stem}_errandified.route")


def _route_pairs(source, output):
    if source.is_dir():
        output.mkdir(parents=True, exist_ok=True)
        return tuple(
            (path, output / path.name)
            for path in sorted(source.glob("*.route"))
        )
    if not source.is_file():
        raise ValueError(f"Input route does not exist: {source}")
    if output.exists() and output.is_dir():
        output = output / source.name
    return ((source, output),)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument("--player", choices=available_player_profiles())
    parser.add_argument(
        "--max-errand-size",
        type=int,
        default=DEFAULT_MAX_ERRAND_SIZE,
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.max_errand_size <= 0:
        parser.error("--max-errand-size must be greater than zero")

    output = args.output or _default_output(args.source)
    try:
        pairs = _route_pairs(args.source, output)
        if not pairs:
            raise ValueError(f"No .route files found in {args.source}")
        if not args.overwrite:
            existing = [destination for _, destination in pairs if destination.exists()]
            if existing:
                raise FileExistsError(f"Route already exists: {existing[0]}")
        for source, destination in pairs:
            plan = load_route(source)
            player = load_player_profile(args.player or plan.player_profile)
            errands = errandify_plan(plan, player, args.max_errand_size)
            saved = save_errandified_route(
                destination,
                plan,
                player,
                errands,
                args.max_errand_size,
                overwrite=args.overwrite,
            )
            print(saved)
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

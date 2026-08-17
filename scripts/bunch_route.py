#!/usr/bin/env python3

"""Experimentally regroup a fixed singleton route into errands."""

import argparse
import sys
from dataclasses import replace
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.algorithms.contiguous_errand_bunching import (
    ALGORITHM_NAME,
    DEFAULT_MAX_ERRAND_SIZE,
    bunch_contiguous_actions,
)
from src.routes import initial_gamestate, load_route, write_route


def bunch_plan(plan, max_errand_size=DEFAULT_MAX_ERRAND_SIZE):
    if plan.errands_enabled or any(len(errand) != 1 for errand in plan.errands):
        raise ValueError("Input route must contain singleton errands")
    return bunch_contiguous_actions(
        initial_gamestate(plan),
        plan.actions,
        max_errand_size,
    )


def save_bunched_route(
    destination,
    plan,
    errands,
    max_errand_size=DEFAULT_MAX_ERRAND_SIZE,
    *,
    overwrite=False,
):
    bunched = replace(
        plan,
        algorithm=ALGORITHM_NAME,
        errands_enabled=True,
        errands=errands,
        errand_queue_depth=None,
        max_errand_size=max_errand_size,
    )
    return write_route(
        destination,
        bunched,
        comment="Contiguous purchases bunched by scripts/bunch_route.py.",
        overwrite=overwrite,
    )


def _default_output(source):
    if source.is_dir():
        return source.parent / "erranded"
    if source.parent.name == "singletons":
        return source.parent.parent / "erranded" / source.name
    return source.with_name(f"{source.stem}_erranded.route")


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
    parser = argparse.ArgumentParser(
        description=(
            "Greedily bunch a singleton route into contiguous age-scored errands"
        )
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path, nargs="?")
    parser.add_argument(
        "--max-errand-size",
        type=int,
        default=DEFAULT_MAX_ERRAND_SIZE,
        help=(
            "maximum contiguous actions per candidate "
            f"(default: {DEFAULT_MAX_ERRAND_SIZE})"
        ),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing output route files",
    )
    args = parser.parse_args(argv)
    if args.max_errand_size <= 0:
        parser.error("--max-errand-size must be greater than zero")

    output = args.output or _default_output(args.source)
    try:
        pairs = _route_pairs(args.source, output)
        if not pairs:
            raise ValueError(f"No .route files found in {args.source}")
        if not args.overwrite:
            existing = [
                destination
                for _, destination in pairs
                if destination.exists()
            ]
            if existing:
                raise FileExistsError(f"Route already exists: {existing[0]}")
        for source, destination in pairs:
            plan = load_route(source)
            errands = bunch_plan(plan, args.max_errand_size)
            saved = save_bunched_route(
                destination,
                plan,
                errands,
                args.max_errand_size,
                overwrite=args.overwrite,
            )
            print(saved)
    except (FileExistsError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

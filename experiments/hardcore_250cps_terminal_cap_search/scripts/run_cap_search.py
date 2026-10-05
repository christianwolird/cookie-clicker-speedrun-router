#!/usr/bin/env python3

"""Search finite-run terminal inventories by recursively capping buildings."""

import argparse
from dataclasses import dataclass, replace
import json
from pathlib import Path
import sys
from time import monotonic


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ccsr.config import load_errand_profile, load_player_profile
from ccsr.routes import (
    RouteAction, RouteResult, action_errands, apply_errand, execute_route,
    load_route, write_route,
)
from ccsr.routing_algorithms.greedy_router import find_route as find_greedy_route


EXPERIMENT = Path(__file__).resolve().parent.parent
RESULTS = EXPERIMENT / "results"
BASE_ROUTE = ROOT / "routes/hardcore-250cps/generated_greedy.route"
DHA_ROUTE = ROOT / "routes/hardcore-10cps/community_errandified_dha.route"


@dataclass(frozen=True)
class Candidate:
    number: int
    depth: int
    caps: tuple[tuple[str, int], ...]
    result: RouteResult


def cap_key(caps):
    return tuple(sorted(caps.items()))


def action_count(result):
    return sum(len(errand) for errand in result.errands)


def final_counts(result):
    return {
        name: count
        for name, count in result.final_gamestate.building_counts.items()
        if count
    }


def violates_caps(state, actions, caps):
    counts = dict(state.building_counts)
    for action in actions:
        if action.operation == "buy":
            counts[action.item] += action.quantity
        elif action.operation == "sell":
            counts[action.item] -= action.quantity
    return any(counts[name] > maximum for name, maximum in caps.items())


def reroute_with_caps(parent, caps, target, options):
    """Retain the parent prefix until the first newly forbidden purchase."""
    state = parent.initial_gamestate.copy()
    prefix = []
    for errand in parent.errands:
        actions = tuple(RouteAction.from_purchase(purchase) for purchase in errand)
        if violates_caps(state, actions, caps):
            break
        state, purchases = apply_errand(state, actions)
        prefix.append(purchases)

    tail = find_greedy_route(
        state,
        target,
        price_horizon_multiplier=options.price_horizon_multiplier,
        queue_expansions=options.queue_expansions,
        max_errand_actions=options.max_errand_actions,
        building_caps=caps,
    )
    return (
        RouteResult(parent.initial_gamestate, tail.final_gamestate,
                    tuple(prefix) + tail.errands),
        len(prefix),
    )


def save_route(path, source_plan, result, caps):
    cap_text = ", ".join(f"{name}<={maximum}" for name, maximum in sorted(caps.items()))
    plan = replace(
        source_plan,
        name=path.stem,
        source="terminal-cap search",
        algorithm="terminal_cap_greedy",
        errands=action_errands(result),
        ruler_route=None,
    )
    write_route(
        path,
        plan,
        comment=(
            "Replay-verified recursive terminal-inventory cap search; "
            f"caps: {cap_text or 'none'}."
        ),
        overwrite=True,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--beam-width", type=int, default=16)
    parser.add_argument("--max-depth", type=int, default=12)
    parser.add_argument("--max-evaluations", type=int, default=500)
    parser.add_argument("--seconds", type=float, default=300)
    parser.add_argument("--near-miss-seconds", type=float, default=2.0)
    parser.add_argument("--queue-expansions", type=int, default=100)
    parser.add_argument("--price-horizon-multiplier", type=float, default=2.0)
    parser.add_argument("--max-errand-actions", type=int, default=100)
    args = parser.parse_args(argv)
    if min(args.beam_width, args.max_depth, args.max_evaluations,
           args.queue_expansions, args.max_errand_actions) <= 0:
        parser.error("integer search limits must be positive")
    if args.seconds <= 0 or args.near_miss_seconds < 0:
        parser.error("time limits must be nonnegative and --seconds must be positive")

    RESULTS.mkdir(parents=True, exist_ok=True)
    source_plan = load_route(BASE_ROUTE)
    player = load_player_profile("default_250_cps")
    single = load_errand_profile("single_no_selling")
    base = execute_route(source_plan, player=player, errand_profile=single)
    dha = execute_route(load_route(DHA_ROUTE), player=player, errand_profile=single)
    target = source_plan.target
    building_order = tuple(base.initial_gamestate.building_catalog)

    started = monotonic()
    serial = 0
    root = Candidate(serial, 0, (), base)
    best = root
    frontier = [root]
    seen = {root.caps}
    records = []
    evaluations = 0
    termination = "depth_limit"

    print(f"Base finish: {base.final_gamestate.age:.9f}", flush=True)
    print(f"DHA finish:  {dha.final_gamestate.age:.9f}", flush=True)

    for depth in range(1, args.max_depth + 1):
        children = []
        for parent in frontier:
            parent_caps = dict(parent.caps)
            counts = parent.result.final_gamestate.building_counts
            for building in building_order:
                if counts[building] <= 0:
                    continue
                child_caps = dict(parent_caps)
                child_caps[building] = min(
                    child_caps.get(building, counts[building]),
                    counts[building] - 1,
                )
                key = cap_key(child_caps)
                if key in seen:
                    continue
                if evaluations >= args.max_evaluations:
                    termination = "evaluation_limit"
                    break
                if monotonic() - started >= args.seconds:
                    termination = "time_limit"
                    break
                seen.add(key)
                child_result, prefix_length = reroute_with_caps(
                    parent.result, child_caps, target, args,
                )
                evaluations += 1
                serial += 1
                child = Candidate(serial, depth, key, child_result)
                children.append(child)
                age = child_result.final_gamestate.age
                row = {
                    "number": serial,
                    "parent": parent.number,
                    "depth": depth,
                    "branch_building": building,
                    "caps": child_caps,
                    "retained_prefix_errands": prefix_length,
                    "finish_seconds": age,
                    "delta_from_base_seconds": age - base.final_gamestate.age,
                    "delta_from_dha_seconds": age - dha.final_gamestate.age,
                    "errands": len(child_result.errands),
                    "actions": action_count(child_result),
                    "final_counts": final_counts(child_result),
                }
                records.append(row)
                if age < best.result.final_gamestate.age:
                    best = child
                    save_route(
                        RESULTS / "best_cap.route", source_plan, best.result,
                        dict(best.caps),
                    )
                    print(
                        f"Improved #{serial} depth={depth} finish={age:.9f} "
                        f"delta_DHA={age - dha.final_gamestate.age:+.6f} "
                        f"caps={dict(best.caps)}",
                        flush=True,
                    )
            if termination in {"evaluation_limit", "time_limit"}:
                break
        if not children:
            if termination == "depth_limit":
                termination = "frontier_exhausted"
            break
        children.sort(key=lambda candidate: candidate.result.final_gamestate.age)
        threshold = best.result.final_gamestate.age + args.near_miss_seconds
        eligible = [
            candidate for candidate in children
            if candidate.result.final_gamestate.age <= threshold
        ]
        frontier = (eligible or children)[:args.beam_width]
        print(
            f"Depth {depth}: evaluated={evaluations}, "
            f"level_best={children[0].result.final_gamestate.age:.9f}, "
            f"global_best={best.result.final_gamestate.age:.9f}, "
            f"next_frontier={len(frontier)}",
            flush=True,
        )
        if termination in {"evaluation_limit", "time_limit"}:
            break

    if best is root:
        save_route(RESULTS / "best_cap.route", source_plan, base, {})
    elapsed = monotonic() - started
    summary = {
        "experiment": "hardcore_250cps_terminal_cap_search",
        "base_route": str(BASE_ROUTE.relative_to(ROOT)),
        "dha_route": str(DHA_ROUTE.relative_to(ROOT)),
        "settings": {
            "version": source_plan.version,
            "player_profile": player.name,
            "click_rate": player.click_rate,
            "errand_delay": player.errand_delay,
            "action_delay": player.action_delay,
            "errand_profile": single.name,
            "target": target,
        },
        "search": vars(args),
        "termination": termination,
        "elapsed_seconds": elapsed,
        "evaluations": evaluations,
        "base_finish_seconds": base.final_gamestate.age,
        "dha_finish_seconds": dha.final_gamestate.age,
        "best_finish_seconds": best.result.final_gamestate.age,
        "best_delta_from_base_seconds": (
            best.result.final_gamestate.age - base.final_gamestate.age
        ),
        "best_delta_from_dha_seconds": (
            best.result.final_gamestate.age - dha.final_gamestate.age
        ),
        "best_caps": dict(best.caps),
        "best_final_counts": final_counts(best.result),
        "best_errands": len(best.result.errands),
        "best_actions": action_count(best.result),
        "records": records,
    }
    (RESULTS / "search_results.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps({key: value for key, value in summary.items() if key != "records"}, indent=2))


if __name__ == "__main__":
    main()

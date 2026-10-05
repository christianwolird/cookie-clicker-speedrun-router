#!/usr/bin/env python3

"""Publish the replay-verified best terminal-cap result to the route catalog."""

from dataclasses import replace
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "src"
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))

from ccsr.config import (
    create_initial_gamestate, load_errand_profile, load_player_profile,
    load_route_profile,
)
from ccsr.routes import execute_route, load_route, write_route
from ccsr.routing_algorithms.greedy_router import find_route as find_greedy_route


EXPERIMENT = Path(__file__).resolve().parent.parent
SOURCE_ROUTE = EXPERIMENT / "results/best_cap.route"
SEARCH_RESULTS = EXPERIMENT / "results/search_results.json"
DESTINATION = ROOT / "routes/hardcore-250cps/generated_greedy_terminal_cap.route"


def main():
    plan = load_route(SOURCE_ROUTE)
    result = execute_route(plan)
    if result.final_gamestate.lifetime_cookies != plan.target:
        raise ValueError("Best cap route does not reach its target")
    summary = json.loads(SEARCH_RESULTS.read_text())
    profile = load_route_profile("hardcore-250cps")
    player = load_player_profile(profile.player_profile)
    shop = load_errand_profile(profile.errand_profile)
    initial = create_initial_gamestate(
        profile, player, errand_profile=shop,
    )
    regenerated = find_greedy_route(
        initial,
        profile.target,
        price_horizon_multiplier=summary["search"]["price_horizon_multiplier"],
        queue_expansions=summary["search"]["queue_expansions"],
        max_errand_actions=summary["search"]["max_errand_actions"],
        building_caps=summary["best_caps"],
    )
    if regenerated.errands != result.errands:
        raise ValueError("A full capped rerun did not reproduce the saved route")
    published = replace(
        plan,
        name=DESTINATION.stem,
        source="terminal-cap search experiment",
    )
    write_route(
        DESTINATION,
        published,
        comment=(
            "Best replay-verified terminal-cap greedy result; see "
            "experiments/hardcore_250cps_terminal_cap_search/."
        ),
        overwrite=True,
    )
    replay = execute_route(load_route(DESTINATION))
    if replay.final_gamestate.age != result.final_gamestate.age:
        raise ValueError("Published route replay changed its finish time")
    print(f"Published {DESTINATION.relative_to(ROOT)}")
    print(f"Finish: {replay.final_gamestate.age:.9f} seconds")
    print("Full capped rerun matched the prefix-reuse search result")


if __name__ == "__main__":
    main()

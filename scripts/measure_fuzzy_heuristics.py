#!/usr/bin/env python3

"""Compare a global measuring-stick heuristic with full fuzzy completions."""

import argparse
import math
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import fmean


REPOSITORY = Path(__file__).resolve().parents[1]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from src.algorithms.fuzzy_astar import (
    MeasuringStickHeuristic as MeasuringStick,
    find_route,
    fuzzy_remaining_time,
    inventory_key,
)
from src.config import DEFAULT_SETTINGS, available_categories, load_category
from src.gamestate import Gamestate
from src.presentation import format_time


PERCENTILES = (0, 1, 5, 10, 25, 50, 75, 90, 95, 99, 100)


@dataclass(frozen=True, slots=True)
class Observation:
    inventory: tuple
    age: float
    lifetime_cookies: float
    cps: float
    a_raw: float
    b: float
    ratio: float
    inventory_label: str


class Recorder:
    def __init__(self, stick, target, price_horizon_multiplier):
        self.stick = stick
        self.target = target
        self.price_horizon_multiplier = price_horizon_multiplier
        self.observations = []
        self.by_inventory = {}

    def _inventory_label(self, gamestate):
        buildings = [
            f"{name}={quantity}"
            for name, quantity in gamestate.building_counts.items()
            if quantity
        ]
        upgrades = sorted(gamestate.purchased_upgrades)
        parts = buildings[:5]
        if len(buildings) > 5:
            parts.append(f"+{len(buildings) - 5} buildings")
        if upgrades:
            parts.append("upgrades=" + ", ".join(upgrades[:3]))
            if len(upgrades) > 3:
                parts.append(f"+{len(upgrades) - 3} upgrades")
        return "; ".join(parts) or "empty"

    def observe(self, gamestate, _search_heuristic):
        a_raw = self.stick.remaining_time(gamestate.lifetime_cookies)
        b = fuzzy_remaining_time(
            gamestate,
            self.target,
            self.price_horizon_multiplier,
        )
        ratio = a_raw / b if b > 0 else math.nan
        observation = Observation(
            inventory=inventory_key(gamestate),
            age=gamestate.age,
            lifetime_cookies=gamestate.lifetime_cookies,
            cps=gamestate.cps(),
            a_raw=a_raw,
            b=b,
            ratio=ratio,
            inventory_label=self._inventory_label(gamestate),
        )
        self.observations.append(observation)
        previous = self.by_inventory.get(observation.inventory)
        if previous is None or observation.age < previous.age:
            self.by_inventory[observation.inventory] = observation


def _initial_gamestate(settings):
    gamestate = Gamestate(settings["version"])
    if settings["initial_state"] == "neverclick":
        gamestate.initialize_neverclick()
    else:
        gamestate.click_rate = settings["click_rate"]
    gamestate.errand_duration = settings["errand_duration"]
    gamestate.purchase_click_rate = settings["purchase_click_rate"]
    gamestate.upgrades_allowed = settings["upgrades_enabled"]
    return gamestate


def _quantile(sorted_values, percentile):
    if not sorted_values:
        return math.nan
    position = (len(sorted_values) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] + fraction * (
        sorted_values[upper] - sorted_values[lower]
    )


def _summary(observations):
    ratios = sorted(
        observation.ratio
        for observation in observations
        if math.isfinite(observation.ratio)
    )
    violations = sum(
        observation.a_raw > observation.b + 1e-9
        for observation in observations
    )
    return {
        "count": len(observations),
        "violations": violations,
        "violation_percent": 100 * violations / len(observations),
        "mean": fmean(ratios),
        **{
            f"p{percentile}": _quantile(ratios, percentile)
            for percentile in PERCENTILES
        },
    }


def _lifetime_bands(target):
    bounds = [0.0, 100.0]
    while bounds[-1] < target:
        bounds.append(min(float(target), bounds[-1] * 10))
    return tuple(zip(bounds, bounds[1:]))


def _print_summary_table(scopes):
    print(
        "| Scope | N | A_raw > B | Mean | Min | P05 | P25 | "
        "Median | P75 | P95 | Max |"
    )
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for label, observations in scopes:
        summary = _summary(observations)
        print(
            f"| {label} | {summary['count']:,} | "
            f"{summary['violations']:,} "
            f"({summary['violation_percent']:.2f}%) | "
            f"{summary['mean']:.4f} | {summary['p0']:.4f} | "
            f"{summary['p5']:.4f} | {summary['p25']:.4f} | "
            f"{summary['p50']:.4f} | {summary['p75']:.4f} | "
            f"{summary['p95']:.4f} | {summary['p100']:.4f} |"
        )


def _print_band_table(observations, target):
    grouped = defaultdict(list)
    bands = _lifetime_bands(target)
    for observation in observations:
        for lower, upper in bands:
            if lower <= observation.lifetime_cookies < upper:
                grouped[(lower, upper)].append(observation)
                break

    print("| Lifetime cookies | N | A_raw > B | Median | P95 | Max |")
    print("|---|---:|---:|---:|---:|---:|")
    for band in bands:
        samples = grouped[band]
        if not samples:
            continue
        summary = _summary(samples)
        lower, upper = band
        print(
            f"| {lower:,.0f}–{upper:,.0f} | {summary['count']:,} | "
            f"{summary['violations']:,} | {summary['p50']:.4f} | "
            f"{summary['p95']:.4f} | {summary['p100']:.4f} |"
        )


def _print_worst(observations, limit=5):
    worst = sorted(observations, key=lambda item: item.ratio, reverse=True)[:limit]
    print("| Ratio | Life | Age | CpS | A_raw | B | Inventory |")
    print("|---:|---:|---:|---:|---:|---:|---|")
    for observation in worst:
        print(
            f"| {observation.ratio:.4f} | "
            f"{observation.lifetime_cookies:,.1f} | "
            f"{observation.age:.3f} | {observation.cps:,.3f} | "
            f"{observation.a_raw:.3f} | {observation.b:.3f} | "
            f"{observation.inventory_label} |"
        )


def measure_category(category):
    settings = {**DEFAULT_SETTINGS, **load_category(category)}
    initial = _initial_gamestate(settings)
    stick = MeasuringStick(
        initial,
        settings["target"],
        settings["price_horizon_multiplier"],
    )
    recorder = Recorder(
        stick,
        settings["target"],
        settings["price_horizon_multiplier"],
    )

    def progress(snapshot):
        print(
            f"{category}: runtime {format_time(snapshot.elapsed_seconds)}, "
            f"{snapshot.expanded:,} expanded, "
            f"{len(recorder.observations):,} measured",
            flush=True,
        )

    print(
        f"Measuring {category}: target {settings['target']:,}, "
        f"{settings['astar_feelers']} feelers, "
        f"inner {settings['astar_inner_search']}, "
        f"heuristic {settings['astar_heuristic']}, "
        f"scale {settings['astar_fuzzy_scale']:g}",
        flush=True,
    )
    result = find_route(
        initial,
        settings["target"],
        price_horizon_multiplier=settings["price_horizon_multiplier"],
        queue_pops=settings["errand_queue_depth"],
        feelers=settings["astar_feelers"],
        inner_search=settings["astar_inner_search"],
        fuzzy_heuristic=settings["astar_heuristic"],
        fuzzy_scale=settings["astar_fuzzy_scale"],
        max_expansions=settings["astar_max_expansions"],
        on_progress=progress,
        progress_interval=30,
        on_heuristic=recorder.observe,
    )

    all_observations = tuple(recorder.observations)
    unique_observations = tuple(recorder.by_inventory.values())
    print(f"\n## {category}")
    print(
        f"Reference fuzzy route: {format_time(stick.final_age)}, "
        f"{len(stick.route.errands)} purchases. "
        f"Measured search route: {format_time(result.final_gamestate.age)}."
    )
    print("\n### Overall A_raw/B distribution\n")
    _print_summary_table(
        (
            ("All scoring events", all_observations),
            ("Unique inventories", unique_observations),
        )
    )
    print("\n### Unique inventories by lifetime band\n")
    _print_band_table(unique_observations, settings["target"])
    print("\n### Five largest A_raw/B ratios\n")
    _print_worst(unique_observations)
    print()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description=(
            "Compare global measuring-stick and state-specific full fuzzy "
            "completion heuristics during fuzzy-A* search"
        )
    )
    parser.add_argument(
        "categories",
        nargs="*",
        choices=available_categories(),
        default=("10k", "100k"),
    )
    args = parser.parse_args(argv)
    for category in args.categories:
        measure_category(category)


if __name__ == "__main__":
    main()

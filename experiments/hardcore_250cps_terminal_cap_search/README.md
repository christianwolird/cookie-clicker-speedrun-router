# Hardcore 250 CPS terminal-cap search

This experiment corrects the finite-horizon failure of the otherwise strong
building-only greedy ordering used for Hardcore. The unrestricted greedy route
saves for a fifth Time Machine near the end of the run. Recursive building
caps search alternate terminal inventories while retaining each parent route's
unchanged prefix and rerouting only from the first forbidden purchase.

Start with [the results summary](docs/SUMMARY.md). Machine-readable results and
the replay-verified best route are under `results/`.

## Reproduce

From the repository root:

```sh
python3 experiments/hardcore_250cps_terminal_cap_search/scripts/run_cap_search.py \
  --max-depth 12 --beam-width 16 --max-evaluations 500 \
  --seconds 300 --near-miss-seconds 2

python3 experiments/hardcore_250cps_terminal_cap_search/scripts/publish_best.py
python3 scripts/replay_route.py \
  routes/hardcore-250cps/generated_greedy_terminal_cap.route
```

The search uses the canonical x1 greedy route as its root and replays DHA with
the same `default_250_cps` player and current `single_no_selling` executor.
Every reported result therefore uses game 1.0466, 250 clicks/s, 0.8 seconds per
errand, 0.2 seconds per action, x1 buying, no selling, and no upgrades.

## Method

At each search depth, every retained route is branched once per owned building
type. A child lowers that building's maximum count by one, retains the parent
prefix until the first errand that would violate any cap, and resumes the
ordinary greedy router from that exact simulator state. The best 16 children
within two seconds of the incumbent continue to the next depth. Cap vectors
are deduplicated globally.

This is a bounded heuristic search, not an optimality proof. It completed six
depths before its five-minute wall-clock limit. Interacting cap reductions
outside the retained frontier may contain a better route.

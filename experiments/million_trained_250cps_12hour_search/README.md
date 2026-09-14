# Trained 250 CPS search experiments

These experiments target one million lifetime cookies in game 2.031 with
`trained_250_cps`: 250 clicks/s, 0.4 seconds per errand, 0.1 seconds per shop
action, fixed ×10 buying and no selling. The native model is deliberately
restricted to this setup. Python replay remains the validation authority.

Start with the [summary of discoveries and results](docs/SUMMARY.md).
The [research log](docs/trained-250cps-12h-search.md) and
[measurements](docs/trained-250cps-search-results.json) preserve the full investigation.
The standalone Python routers continue to work without a C++ compiler.

`scripts/` contains the Python entry points, native sources, tests and supporting
data. `docs/` contains the session's reports and proofs. Archived measurements
retain original paths inside historical parameters, source-hash keys and route
snapshots; their `file_relocation` metadata maps the old layout to this one.

## Reproduce the inexpensive recipe

From the repository root, with Python 3 and a C++17 compiler installed:

```sh
export CCSR_EXPERIMENT_DIRECTORY=/tmp/ccsr-trained-reproduction
python3 experiments/million_trained_250cps_12hour_search/scripts/build_native.py
python3 experiments/million_trained_250cps_12hour_search/scripts/run_fast_recipe.py
```

This starts with greedy choices from the initial game state, then performs
100,000 deterministic local refinement trials. The existing greedy route is
read only as a comparison, not as a source of purchases. Two clean executions
produced 201.485756 seconds greedily and 198.146636 seconds after refinement
in about 9–10 seconds, excluding compilation, on the session's machine. The final fresh build repeated it in 8.80 seconds.
The recipe predates the slightly faster current incumbent.

To reproduce the 198.140717-second incumbent from the initial state, use:

```sh
python3 experiments/million_trained_250cps_12hour_search/scripts/run_best_recipe.py
```

This uses complete greedy continuations to choose errands, then 50,000
refinement trials while preserving its upgrade order. A fresh run produced
200.056548 seconds before refinement and 198.140717 afterward in 208.76 seconds
total, excluding compilation. After exact price, rate and queue optimizations,
a fresh build reproduced both times in 157.11 seconds. The final delivery build repeated them in 178.88 seconds under concurrent load. It reads the route catalog for configuration;
no existing route's purchases are supplied to the planner. Outputs are
`recipe_best_greedy.route`, `recipe_best_refined.route` and `best_recipe.json`.

The policy driver also accepts `rollout-bonuses` as a comma-separated string
(e.g. `"0,0.05,0.1,0.2"`) to compare complete continuations from several greedy
policies. `upgrade-bonus` adjusts the outer candidate generator. Neither option
changes simulated purchase costs or timing. Their default is the original
single bonus of zero; this additional ensemble is experimental.

Outputs include `recipe_greedy.route`, `recipe_refined.route`, their replay
results, logs, parameters and source snapshots. Use a fresh output directory
for independent repetitions. Session-specific audit and sweep scripts retain
their original paths; the build, recipe and main search entry points honor
`CCSR_EXPERIMENT_DIRECTORY`.

## Run a bounded beam experiment

```sh
python3 experiments/million_trained_250cps_12hour_search/scripts/run_native_beam.py trial_name \
  --source routes/million-250cps/generated_beam.route --seconds 600 \
  --options-json '{"width":2000,"inner":2000,"pops":6000,"workers":2,"horizon":0,"anchor":4,"macro":1,"future-mask":32768,"future-inventory":0.03,"canonical-partials":1,"quantity-children":4,"age-bound":1,"persistent-workers":1,"stage-balance":1,"seed-prefixes":0,"target-rollout":1,"rollout-weight":0.5,"hint-slack":1,"rollout-keep":160,"rollout-raw":40,"completion-cache":100000,"compact":1,"retain-closed":1,"heap":300000,"nodes":3000000,"report-generated":1}'
```

The wrapper replays every reported improvement, retained candidate and final
completion. The ordinary result can be the supplied incumbent if search finds
nothing faster. `trial_name_generated.route` records the best completion
constructed by expanded errands, excluding ruler-suffix rollouts. The ruler
still influences its ranking and pruning.

Useful experimental controls:

| Option | Meaning |
|---|---|
| `width`, `inner`, `pops` | Returned pool size, inner queue size and inner expansion budget |
| `quantity-children: 4` | Grow quantities to the next feasible basket; avoid shuffled single-item additions |
| `future-mask: 32768` | Include prospective Plastic mouse value in local ranking |
| `future-inventory` | Forecast additional inventory from a later point on the ruler |
| `inventory-cap: N`, `upgrade-cap: 1` | Restrict generated inventories to initial-ruler counts plus N, and optionally its upgrades |
| `rollout-keep`, `rollout-raw` | Retain completion-ranked candidates, reserving some local-score choices |
| `completion-cache` | Per-worker bounded cache of completion ranking estimates |
| `refresh-hints: 1` | Recompute queued completion estimates when the dynamic ruler improves |
| `shared-ruler` | Adopt a faster published native-format ruler between batches |
| `stage-balance: 1` | Share expansions across produced-cookie ranges |
| `batch-size` | Queue this many tasks per batch; defaults to worker count, requires persistent workers for prefetch |
| `start-prefix` | Fix this many source errands; restricts the searched opening |
| `expansions` | Stop after a fixed number of outer expansions |
| `harvest`, `harvest-strategy: 1` | Keep near misses with different upgrade orders for later refinement |
| `harvest-strategy: 3`, `harvest-order-limit` | Also distinguish route shapes, with a cap per upgrade order |

Inventory caps are a heuristic restriction fixed from the initial source,
not a dominance rule. They constrain generated errands; adopted incumbents
and ruler continuations can remain outside that restricted region.

Larger batches can reduce idle time but delay feedback from newly generated routes,
so they also change the searched trajectory. The explicit expansion budget is
clipped at the final batch; it is not rounded up to a whole worker batch.

Ruler completion is a feasible upper bound, not an admissible lower bound.
Candidate selection, price horizons, bounded queues and ruler pruning can all
exclude a better route. A best-found result is not an optimality certificate.

## Refine or inspect a route

`run_native_local.py` performs order, quantity and partition refinement. For
example, add `--source PATH --seconds 300 --width 4 --blocks --cache-size 100000`.
`--quantity-order 3` instead systematically changes exactly three building
purchase quantities and repartitions each resulting sequence. A completed
scan certifies only that finite neighborhood under the chosen partition width.
`--quantity-start N --quantity-end M` evaluates the half-open combination
range [N, M) around one fixed source sequence. It can resume a previous range
or divide the neighborhood among independent workers. `next_index` records
the first unprocessed combination; resume using the same original source,
order and partition width, not the improved output route. A finished range
does not certify any combinations outside its bounds.
`--aggregate-partition` collects building totals within each proposed errand
and applies the canonical fixed-x10 order. It can combine nonadjacent purchases;
add `--expand --max-size 128` to permit boundaries within recorded quantities.
This changes the refinement neighborhood and is optional.
`systematic_polish.py` checks common single-action edits and quantity pairs.

To stop a main native trial cooperatively, create
`$CCSR_EXPERIMENT_DIRECTORY/trial_name.stop`. The process emits its current
result and exits normally. Keep trial names unique; wrappers hold a filesystem
lock to prevent concurrent writers. An old stop file also stops a repeated
trial of the same name. Ctrl-C in a controller is not sufficient evidence that
all descendant processes have stopped in this execution environment.

Main native wrappers retain the actual executable and its SHA-256 alongside
the source snapshot. Long campaign trials can share the verified incumbent
through `publish_incumbent.py`, which publishes a native seed file while
`track_best.py` remains the sole owner of the global route checkpoint. Adoption
is recorded as `external_incumbent`, separately from a trial's own discoveries.
The generated-only result still excludes those adopted routes and suffix
rollouts. Both publisher scripts currently use this session's end time.

## Verification

```sh
python3 -m unittest discover -s experiments/million_trained_250cps_12hour_search/scripts -p 'test_*.py'
PYTHONPATH=src python3 -m unittest discover -s tests
```

The `audit_*`, `verify_*` and `benchmark_*` programs preserve focused checks
used during development. Many are session-specific measurements rather than
general project tests. Exact normalization rules are documented separately in
[the partial-purchase ordering proof](docs/x10-partial-purchase-order.md).

### Mixed quantity changes and purchase deletions

`run_native_local.py --quantity-order K --quantity-deletions` scans only
combinations where at least one selected building purchase is deleted (quantity
zero). Other selected quantities can take any value from 0 through 10 except
their original value. This complements the positive-only scan without repeating
its combinations. Upgrades and the remaining action order stay fixed; each
candidate is repartitioned into errands. The `--quantity-start` and
`--quantity-end` indices refer to this deletion-only enumeration when the flag
is enabled. Its combinatorial count and shard fingerprints are tested against
an independent Cartesian-product enumeration.

### Dense small quantity changes

`run_native_local.py --quantity-cube-minimum 6` changes each building purchase
by at most one (clamped to 0–10), requiring at least six changed positions.
Zero deletes the purchase. This searches many coordinated small changes that
an exhaustive scan of up to five changed positions cannot reach. It keeps
upgrades and the remaining action order fixed and repartitions each sequence.
The same half-open `--quantity-start` / `--quantity-end` controls apply, but
indices belong to this dense enumeration. Use the identical original source
when resuming. The scanner supports up to 32 building-purchase positions;
Cartesian-oracle tests cover the count, ordering, shards and resumption.

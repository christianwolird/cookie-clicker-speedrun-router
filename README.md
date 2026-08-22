# Cookie Clicker speedrun router

A small, dependency-free simulator and heuristic route generator for no-golden-
cookie Cookie Clicker speedruns. The project currently focuses on the first
million cookies, while also carrying presets and comparison routes for
Neverclick, Hardcore, and the first heavenly chip.

The router models buildings, upgrades, achievements, hand clicking, shop
downtime, and grouped shopping trips called errands. It is research software:
stored routes are reproducible under the model, but generated routes are not
claimed to be globally optimal.

## Quick start

Python 3.10 or newer is sufficient; there are no third-party runtime
dependencies.

```sh
python3 make_route.py --category one_million
python3 make_route.py --category one_million --verbose
python3 make_route.py --category heavenly_chip --click-rate 15
```

Save a generated route under `routes/local/`:

```sh
python3 make_route.py \
  --category one_million \
  --save routes/local/errand_queueing/one_million_10_cps.route \
  --overwrite
```

Category files provide defaults. Explicit command-line options take precedence:

```sh
python3 make_route.py --category one_million --click-rate 15
python3 make_route.py --category hardcore --allow-upgrades
python3 make_route.py --category neverclick --initial-state fresh --click-rate 10
```

Run `python3 make_route.py --help` for the complete option list.

## Simulation model

A `Gamestate` is a snapshot with zero cookies banked. It records elapsed time,
lifetime cookies, handmade cookies, owned buildings, purchased upgrades, and
earned achievements. The selected game version supplies all prices, production
values, unlock requirements, and achievement thresholds.

An errand is an unordered set of purchases made during one trip to the shop.
All its purchases close simultaneously. Buying several Cursors counts as one
purchase type; buying Cursors, Farms, and an upgrade counts as three.

The default shop timing is:

```text
travel time             = 1.0 second per errand
purchase click rate     = 5 distinct purchase types per second
pause                   = travel time + purchase types / click rate
```

If `A` is automatic CpS, `H` is hand CpS, `P` is the errand price, and `T` is
the time until the errand closes, the player stops hand-clicking during the
pause:

```text
(A + H) × (T - pause) + A × pause = P
T = (P + H × pause) / (A + H)
```

This is why purchase time is not simply `price / total CpS`. Both timing values
can be changed from `make_route.py` and are stored in generated route files.

The zero-bank, simultaneous-close approximation intentionally ignores cookies
produced by new buildings during the errand and any bank remaining when the
mouse returns to the big cookie. Sales are represented as immediate credit
toward later purchases. A sale returns one quarter of the previous purchase
price, calculated from the current buy price as `current price × 0.25 / 1.15`.

## Route generation

`errand_queueing` is the default and primary algorithm. At each gamestate it:

1. Seeds candidates with each building and each upgrade. A locked upgrade seed
   includes the buildings still needed to unlock it.
2. Rejects errands whose total sticker price exceeds the moving price horizon.
   The default horizon is twice current lifetime cookies, with a 1,000-cookie
   floor.
3. Age-scores valid candidates and places promising errands in a priority
   queue.
4. Repeatedly adds one building or upgrade to queued errands, deduplicating
   unordered purchase sets and pruning candidates whose effective-cost lower
   bound cannot beat the best score found.
5. Executes the best viable errand and repeats from its child gamestate.

The default queue budget is 100 pops per gamestate. Change the two main search
bounds with:

```sh
python3 make_route.py \
  --category one_million \
  --price-horizon-multiplier 4 \
  --errand-queue-depth 250
```

`singleton_errands` uses the same scoring and candidate seeds but permits only
one purchase per errand. Neverclick uses this mode because pausing hand clicks
has no cost when the click rate is zero.

`fuzzy_astar` is the experimental multi-errand planner. Inventories are graph
vertices and candidate errands are outgoing edges. The search retains the
youngest known gamestate for each inventory and lazily discards older queue
entries when they are popped. Its priority is the state's age plus a scaled
zero-purchase-delay singleton estimate to completion. By default, one complete
fuzzy route is generated from the initial state and used as a measuring stick:
each node's lifetime cookies are interpolated onto that route, so scoring a
node never generates another fuzzy route. The slower `individual` heuristic
instead recalculates a complete fuzzy route from each node.

The default `bounded_beam` inner search uses the feeler count as both its live
queue width and its returned-errand roster size. It stops once the roster is
full and the best queued errand scores worse than the roster's worst member.
Because an errand extension can improve on its prefix's score, this is an
intentional beam-search approximation. Increasing the feeler count lets more
such prefixes survive. The prior fixed-pop search remains available for direct
comparisons.

The errand beam width, heuristic choice and scale, and hard expansion limit are
explicit runtime/quality knobs:

```sh
python3 make_route.py \
  --category 100k \
  --astar-inner-search bounded_beam \
  --astar-feelers 20 \
  --astar-heuristic measuring_stick \
  --astar-fuzzy-scale 1.0 \
  --astar-max-expansions 10000
```

Select the older inner search or the per-node heuristic with:

```sh
python3 make_route.py \
  --category 100k \
  --astar-inner-search fixed_pops \
  --errand-queue-depth 30 \
  --astar-heuristic individual
```

This is A*-style rather than a proof-producing A*: the top-k edge generator is
incomplete, measuring-stick interpolation is approximate, and the fuzzy-scale
assumption is empirical. Increasing feelers or the expansion limit trades
runtime for a better chance of finding a faster route. Scales above 1 are
accepted for experiments, though they weight the approximate heuristic more
aggressively and may terminate before exploring useful detours. Older cookie-
scoring and one-purchase age-scoring outputs remain under `routes/local/` as
historical baselines, but their obsolete generator implementations have been
removed.

Long fuzzy-A* runs print a three-line progress snapshot every 30 seconds. It
includes runtime, search counts, the incumbent finish, queue size, and the top
three live frontier states with their incoming errands. Change the cadence
with `--astar-progress-interval SECONDS`.

## Age scoring and its limit

For an ancestor with CpS `c` and a descendant that costs effective price `A`
and adds CpS `a`, the router minimizes:

```text
score = A × (a + c) / a
A = elapsed acquisition time × ancestor CpS
```

This correctly accounts for purchase downtime and the internal elapsed time of
a descendant. It gives a useful local ordering for disjoint, swappable
investments that will all eventually be bought.

It does not supply long-term planning. In particular, the score can undervalue
an upgrade when its main payoff is a run of stronger building purchases after
the upgrade. It also cannot choose an optimal partition by comparing nested
sets such as `{A}`, `{A, B}`, and `{A, B, C}`; those alternatives overlap and
are not swappable purchases. These limitations define the next phase of the
project. See [routing notes](docs/routing-notes.md).

## Stored routes

`.route` files are readable text containing reproducibility metadata followed
by `buy`, `upgrade`, and `sell` actions. An `errand` marker groups the actions
that follow it. A markerless action list is interpreted as singleton errands.

```text
name = example
source = this codebase
version = 2.031
target = 1000000
click_rate = 10
initial_state = fresh
algorithm = errand_queueing
errand_duration = 1.0
purchase_click_rate = 5.0
upgrades_enabled = true
errands_enabled = true
errand_queue_depth = 100

errand
buy Cursor
upgrade Reinforced index finger
```

The route directories are:

```text
routes/
├── dha_spreadsheets/       original community workbooks
├── from_online/
│   ├── singletons/         normalized community purchase orders
│   └── erranded/           DP-errandified community purchase orders
└── local/                  routes generated during this research
```

Replay a route with its recorded settings:

```sh
python3 scripts/replay_route.py \
  routes/from_online/singletons/one_million_fast_clicks_15_cps_dha.route \
  --verbose
```

Replay-time `--version`, `--errand-duration`, and `--purchase-click-rate`
options deliberately override recorded metadata for controlled comparisons.

Regenerate the normalized community routes from the workbooks with:

```sh
python3 scripts/extract_public_routes.py
```

`scripts/errandify.py` partitions a fixed singleton purchase order with
prefix dynamic programming. For every action prefix, it extends the fastest
saved preceding prefix with each valid final errand of 1–100 actions and
retains the fastest result:

```sh
python3 scripts/errandify.py \
  routes/from_online/singletons \
  routes/from_online/erranded \
  --overwrite
```

The tool preserves action order, keeps sales singleton, and defaults to the
canonical `routes/from_online/erranded/` destination. It is not used by
`make_route.py`. Historical fixed-route experiments and measurements are
recorded in `docs/errandification.md`.

## Code layout

```text
make_route.py               route-generation CLI
categories/                 data-driven category defaults
scripts/
├── replay_route.py         deterministic route replay
├── extract_public_routes.py
└── errandify.py            dynamic-programming fixed-route errandification
src/
├── gamestate.py            simulation and purchase mechanics
├── routes.py               route format, I/O, and replay
├── presentation.py         shared terminal table
├── config.py               category configuration
├── algorithms/             current search and scoring
└── data/                    version-specific game catalogs
tests/                      behavioral test suite
```

Game data is split between versions `1.0466` and `2.031`. Upgrade commands use
the proper version-specific names. The hand-written catalogs were checked
against the [Cookie Clicker upgrade table](https://cookieclicker.fandom.com/wiki/Upgrades),
the [achievement table](https://cookieclicker.fandom.com/wiki/Achievement), and
the corresponding game source.

## Tests

```sh
python3 -m unittest discover -v
```

The suite covers simulation math, version data, achievements and kittens,
sales, errand search, route round-trips, every stored route, workbook
extraction, experimental bunching, and both public CLIs.

## Next research direction

The experimental inventory search now plans across multiple errands, but its
candidate generator still emits purchases only. The next major extension is to
generate mixed sell-and-buy errands and measure stabilization as feeler count,
inner method, and fuzzy scale are varied. Achievement effects remain in
the simulated gamestate but are deliberately excluded from inventory identity,
matching the current youngest-age dominance approximation.

Profile results and prospective performance/search improvements are collected
in [A* improvement ideas](docs/improvement_ideas.md). The implemented redesign
and its benchmark results are documented in
[revised A* inventory search](docs/revised_astar.md).

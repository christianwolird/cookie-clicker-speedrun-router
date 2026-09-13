# Cookie Clicker speedrun router

A dependency-free simulator and route-planning toolkit for no-golden-cookie
Cookie Clicker speedruns. The project exposes four primary tools:

- `greedy_router.py` repeatedly executes the best locally scored errand.
- `beam_search_router.py` searches inventory states with a route-based Ruler.
- `errandifier.py` groups a Quickster purchase order into human errands.
- `route_replayer.py` deterministically replays an existing route.

Python 3.10 or newer is sufficient.

## Quick start

Every router run selects a category, player profile, and errand profile independently:

```sh
python3 tools/greedy_router.py \
  --category one_million_v2

python3 tools/beam_search_router.py \
  --category 100k \
  --player casual \
  --beam-width 10
```

Category files under `config/categories/` define game rules such as version,
target, initial state, upgrades, clicking restrictions, and the optional
achievement curve. Use `one_million_v1` for game version 1.0466 or
`one_million_v2` for version 2.031; both target one million cookies. Routers
default to `one_million_v2`.

Player profiles under `config/player_profiles/` define:

```text
click_rate = 7
errand_delay = 1.0
action_delay = 0.3
```

Built-in profiles include `casual`, `scroll_click`, `strum_click`, and
`mouse_move_click`, plus the `default_*` profiles used by imported community
routes. Omitting `--player` selects `default_10_cps`: 10 CPS, 0.8 seconds
per errand, and 0.2 seconds per shop action. Old `item_delay` settings remain
readable as an alias; specifying both names is an error.

Errand profiles under `config/errand_profiles/` select fixed buying behavior:
`single` (the default), `single_with_sales`, `bulk10`, or `bulk10_with_sales`.
There is no switching between x1 and x10 during a run.

```sh
python3 tools/beam_search_router.py \
  --category one_million_v2 --player default_250_cps \
  --errand-profile bulk10 --beam-width 10 \
  --errand-search-width 10 --errand-queue-expansions 100

python3 tools/greedy_router.py \
  --category neverclick --player default_neverclick \
  --errand-profile single_with_sales
```

See [fixed bulk errands](docs/fixed_bulk_errands.md) for action semantics,
sales, search budgets, and route compatibility. The old `quick_buy_250_cps`
profile is retained for reproducing its approximate timing; use realistic
action delays with `bulk10` for new bulk routes.

## Simulation model

A `Gamestate` records elapsed time, lifetime cookies, handmade cookies,
inventory, purchased upgrades, bank, and production. Errands retain grouped
production timing: the ancestor's buildings produce until all actions close.

Every interface action contributes one action delay. Five x1 building
purchases therefore incur:

```text
pause = errand_delay + 5 × action_delay
```

If `A` is automatic CpS, `H` is hand CpS, `P` is the additional cookies needed
after refunds and existing bank, and `T` is the time until the errand closes:

```text
(A + H) × (T - pause) + A × pause = P
T = max(pause, (P + H × pause) / (A + H))
```

Surplus refunds and unavoidable pause production stay in the bank. Fixed x1
errands are unordered sets; fixed x10 purchases are ordered clicks checked
against the remaining bank. Upgrades always take one click. Sales precede
purchases and pay for switching into sell mode and back into buy mode.
Legacy route files retain their original timing and sale behavior.

Achievement objects and repeated catalog scans are not simulated. Categories
may instead select a provisional lifetime-cookie-to-achievement-count curve.
The curve is consulted only for kitten production multipliers; achievements
never gate upgrade availability.

## Greedy routing

The Greedy router searches possible errands from the current gamestate,
executes the best age-scored candidate, and repeats.

All errands compared at one gamestate share the same ancestor CpS `c`. Let
`A` be an errand's acquisition time and `a` its resulting CpS. For two
exchangeable errands `(A, a)` and `(B, b)`, executing A first is faster when:

```text
A + B × c/a < B + A × c/b
A × (1 - c/b) < B × (1 - c/a)
A × a/(a-c) < B × b/(b-c)
```

The common ancestor-CpS factor from the older score does not affect candidate
ordering, so the router uses the cheaper time-valued score:

```text
score(A, a) = A × a/(a-c)
```

The argument assumes the errands do not intersect and that their acquisition
times scale inversely with CpS. The score is a local ordering heuristic when
those assumptions do not hold exactly.

Its main controls are:

```sh
python3 tools/greedy_router.py \
  --category one_million_v2 \
  --player casual \
  --queue-expansions 100 \
  --price-horizon-multiplier 2
```

## Beam search and the Ruler

Beam search treats inventories as graph nodes and generated errands as edges.
It retains the youngest known equivalent gamestate and prioritizes states
using their age plus a scaled remaining-time estimate. Profiled states also
distinguish bank and cookie progress, so sale-funded inventories are not merged
incorrectly. The complete reference route is retained as an incumbent.

The estimate comes from a Ruler route. Supply an existing route with
`--ruler-route`:

```sh
python3 tools/beam_search_router.py \
  --category one_million_v2 \
  --player casual \
  --beam-width 20 \
  --ruler-route routes/generated/greedy_routes/reference.route \
  --ruler-scale 0.9
```

When no Ruler route is supplied, the tool generates a temporary Greedy route
using the same category, player, errand profile, and Quickster mode. The default scale is 0.9.
This is intended to make the estimate conservative, but it is not a proof that
the heuristic is admissible.

## Quickster mode

Quickster versus human execution is independent of routing algorithm. Both
routers accept `--quickster`:

```sh
python3 tools/greedy_router.py --category 10k --player scroll_click --quickster
python3 tools/beam_search_router.py --category 10k --player scroll_click --quickster
```

Quickster mode offers only single-click errands and applies zero errand and action
delay. A bulk click may buy up to ten buildings. Quickster route files set `for_quickster = true` and omit both delay
fields.

## Errandification and replay

See [`docs/erranding_and_quicksters.md`](docs/erranding_and_quicksters.md) for
the timing model, dynamic-programming method, online route catalog, and replay
comparison.

Group a Quickster route for a selected player:

```sh
python3 tools/errandifier.py \
  routes/online/quickster_originals/one_million_fast_clicks_15_cps_dha.route \
  routes/online/erranded/one_million_fast_clicks_15_cps_dha.route \
  --player casual
```

Replay with the route's recorded timing or another player profile:

```sh
python3 tools/route_replayer.py \
  routes/online/quickster_originals/one_million_left_clicks_10_cps_iwer_sonsch.route

python3 tools/route_replayer.py ROUTE_FILE --player casual

# Print purchases at their simulated times, measured from command startup.
python3 tools/route_replayer.py ROUTE_FILE --realtime
```

`--realtime` automatically shows purchase rows and waits until the target time
to print `Done!`. Purchases in the same errand print together. Without this
flag, replay finishes immediately; `--verbose` shows all purchases immediately.

Routes record both the profile name and resolved timing values. This preserves
replay behavior if a profile is later edited. Quickster routes retain only the
profile and resolved click rate because their purchase delays are necessarily
zero.

## Repository layout

```text
tools/                              four primary command-line tools
src/ccsr/
├── game/                           gamestate and versioned game data
├── config/                         category, player, and curve loaders
├── errands/                        errand models, generation, and DP grouping
├── routing_algorithms/             Greedy, Beam search, and Route Ruler
├── routes/                         route models, text format, and replay
└── presentation.py                 terminal route tables
config/
├── categories/
├── player_profiles/
└── achievement_curves/
routes/
├── online/
│   ├── spreadsheets/
│   ├── quickster_originals/
│   └── erranded/
└── generated/
    ├── greedy_routes/
    └── beam_routes/
scripts/extract_online_routes.py    community-workbook importer
tests/                              behavioral test suite
```

Legacy generated routes were removed because they used the former per-item-type
timing rule. Historical timing measurements remain in `docs/`.

Regenerate normalized community originals with:

```sh
python3 scripts/extract_online_routes.py
```

## Tests

```sh
python3 -m unittest discover -v
```

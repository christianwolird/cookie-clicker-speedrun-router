# Cookie Clicker speedrun router

A dependency-free simulator and route-planning toolkit for no-golden-cookie
Cookie Clicker speedruns. The project exposes four primary tools:

- `greedy_router.py` repeatedly executes the best locally scored errand.
- `beam_search_router.py` searches inventory states with a route-based Ruler.
- `errandifier.py` groups a Quickster purchase order into human errands.
- `route_replayer.py` deterministically replays an existing route.

Python 3.10 or newer is sufficient.

## Quick start

Every router run selects a category and player profile independently:

```sh
python3 tools/greedy_router.py \
  --category one_million

python3 tools/beam_search_router.py \
  --category 100k \
  --player casual \
  --beam-width 10
```

Category files under `config/categories/` define game rules such as version,
target, initial state, upgrades, clicking restrictions, and the optional
achievement curve. Player profiles under `config/player_profiles/` define:

```text
click_rate = 7
errand_delay = 1.0
item_delay = 0.3
```

Built-in profiles include `casual`, `scroll_click`, `strum_click`, and
`mouse_move_click`, plus the `default_*` profiles used by imported community
routes. Omitting `--player` selects `default_10_cps`: 10 CPS, 0.8 seconds
per errand, and 0.2 seconds per item.

## Simulation model

A `Gamestate` records elapsed time, lifetime cookies, handmade cookies,
inventory, purchased upgrades, and production. All purchases in an errand
close simultaneously with an empty bank.

Every purchased item contributes its own item delay. Two Grandmas and three
Cursors therefore incur:

```text
pause = errand_delay + 5 × item_delay
```

If `A` is automatic CpS, `H` is hand CpS, `P` is the errand price, and `T` is
the time until the errand closes:

```text
(A + H) × (T - pause) + A × pause = P
T = (P + H × pause) / (A + H)
```

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
  --category one_million \
  --player casual \
  --queue-expansions 100 \
  --price-horizon-multiplier 2
```

## Beam search and the Ruler

Beam search treats inventories as graph nodes and generated errands as edges.
It retains the youngest known gamestate for each inventory and prioritizes
states using their age plus a scaled remaining-time estimate.

The estimate comes from a Ruler route. Supply an existing route with
`--ruler-route`:

```sh
python3 tools/beam_search_router.py \
  --category one_million \
  --player casual \
  --beam-width 20 \
  --ruler-route routes/generated/greedy_routes/reference.route \
  --ruler-scale 0.9
```

When no Ruler route is supplied, the tool generates a temporary Greedy route
using the same category, player, and Quickster mode. The default scale is 0.9.
This is intended to make the estimate conservative, but it is not a proof that
the heuristic is admissible.

## Quickster mode

Quickster versus human execution is independent of routing algorithm. Both
routers accept `--quickster`:

```sh
python3 tools/greedy_router.py --category 10k --player scroll_click --quickster
python3 tools/beam_search_router.py --category 10k --player scroll_click --quickster
```

Quickster mode offers only single-item errands and applies zero errand and item
delay. Quickster route files set `for_quickster = true` and omit both delay
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
```

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

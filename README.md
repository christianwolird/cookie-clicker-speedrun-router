# Cookie Clicker speedrun router

A dependency-free simulator and route-planning toolkit for no-golden-cookie
Cookie Clicker speedruns. The project exposes five primary tools:

- `greedy_router.py` repeatedly executes the best locally scored errand.
- `beam_search_router.py` searches inventory states with a route-based Ruler.
- `errandifier.py` groups a Quickster purchase order into human errands.
- `route_replayer.py` deterministically replays an existing route.
- `route_catalog.py` browses saved routes and named route types.

Python 3.10 or newer is sufficient.

## Quick start and catalog

Choose a named route type, configured in `config/route_profiles/`:

```sh
python3 tools/route_catalog.py profiles
python3 tools/route_catalog.py list --route-type hardcore-10cps
python3 tools/route_catalog.py list --goal one_million --version 2.031

python3 tools/greedy_router.py --route-profile million-250cps --save
python3 tools/beam_search_router.py --route-profile million-25cps --beam-width 10 --save
```

A route profile combines a goal, game version, player profile, and errand
profile. The default is `million-25cps`. `--player`, `--errand-profile`,
and `--version` can override individual settings for experiments; saved files
record their actual values. Each `<category>-<rate>cps` profile holds the chosen
player, errand, and version settings for that category and click rate. Update
that profile when a better setup is established.

| Route type | Goal | Version | Player | Errands |
|---|---|---|---|---|
| `million-250cps` | One million | 2.031 | 250 CPS | x10, no selling |
| `million-25cps` | One million | 2.031 | 25 CPS | x1, no selling |
| `neverclick-0cps` | One million | 2.031 | No ongoing clicks | x1, selling |
| `hardcore-250cps` | One billion, no upgrades | 2.031 | 250 CPS | x10, no selling |

Community comparison types preserve the source workbooks' settings:
`hardcore-10cps`, `heavenly-chip-15cps`, `million-10cps`,
`million-15cps`, and `million-200cps`.

Goals are defined in `src/ccsr/config/goals.py` and have no game version or
clicking method. Neverclick is the one-million goal with the `neverclick`
player profile; that profile supplies the initial 15 clicks and first Cursor.
Hardcore's no-upgrade restriction belongs to its route profile.

The retained player profiles are `default_10_cps`, `default_15_cps`, and
`default_200_cps` for the imported routes, plus `neverclick`, `casual`,
`default_25_cps`, `default_250_cps`, and `trained_250_cps`. The million-250cps
route profile uses the trained profile, with a 0.4-second errand delay and a
0.1-second action delay. Player profiles specify click rate,
errand delay, and action delay; old `item_delay` settings remain readable.

Errand profiles are `single_no_selling`, `single_with_selling`,
`bulk10_no_selling`, and `bulk10_with_selling`.

See [catalog and route organization](docs/route_catalog.md) for browsing,
filters, and save paths, and [fixed bulk errands](docs/fixed_bulk_errands.md)
for execution and search details.

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
  --route-profile million-25cps \
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
  --route-profile million-25cps \
  --player casual \
  --beam-width 20 \
  --ruler-route routes/million-25cps/generated_greedy_reference.route \
  --ruler-scale 0.9
```

When no Ruler route is supplied, the tool generates a temporary Greedy route
using the same category, player, errand profile, and Quickster mode. The default scale is 0.9.
This is intended to make the estimate conservative, but it is not a proof that
the heuristic is admissible.

For the trained 250 CPS setup, the optional
[native search experiments](experiments/million_trained_250cps_12hour_search/README.md) include
canonical ×10 errand generation, parallel beam search, greedy lookahead and
route refinement. The [twelve-hour search summary](experiments/million_trained_250cps_12hour_search/docs/SUMMARY.md)
records the measurements and provides a short recipe for reproducing the best
route from an empty game. These experiments require a C++17 compiler and target
that specific game/player/shop configuration; the ordinary Python tools remain
independent of them.

## Quickster mode

Quickster versus human execution is independent of routing algorithm. Both
routers accept `--quickster`:

```sh
python3 tools/greedy_router.py --route-profile 10k-10cps --player default_25_cps --quickster
python3 tools/beam_search_router.py --route-profile 10k-10cps --player default_25_cps --quickster
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
  routes/million-15cps/community_quickster_dha.route \
  routes/million-15cps/community_errandified_dha.route \
  --player casual
```

Replay with the route's recorded timing or another player profile:

```sh
python3 tools/route_replayer.py \
  routes/million-10cps/community_quickster_iwer_sonsch.route

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
tools/                                  routers, replay, errandification, catalog
src/ccsr/
├── game/                               simulator and versioned game data
├── config/                             goals and profile loaders
├── errands/                            errand models, generation, and grouping
├── routing_algorithms/                 Greedy, Beam search, and Route Ruler
├── routes/                             format, replay, layout, and catalog
└── presentation.py                     terminal route tables
config/
├── route_profiles/                     named route types
├── player_profiles/
├── errand_profiles/
└── achievement_curves/
routes/
├── hardcore-10cps/
│   ├── community_quickster_dha.route
│   ├── community_quickster_lookas123.route
│   ├── community_errandified_dha.route
│   ├── community_errandified_lookas123.route
│   └── generated_greedy.route
├── million-15cps/
│   ├── community_quickster_dha.route
│   ├── community_errandified_dha.route
│   ├── generated_greedy.route
│   └── generated_beam.route
├── million-250cps/generated_greedy.route
├── million-25cps/generated_greedy.route
├── hardcore-250cps/generated_greedy.route
└── ...                                 other named route types
community_spreadsheets/                 original workbooks and their importer
└── extract_routes_from_spreadsheet.py
tests/                                  behavioral test suite
```

Regenerate community originals in their type folders with
`python3 community_spreadsheets/extract_routes_from_spreadsheet.py`. Errandification defaults to the
same type folder with a `community_errandified_` filename prefix; routers use
`generated_greedy_` or `generated_beam_` prefixes when `--save` is supplied.

The eight obsolete or superseded local variants were removed during the layout
migration: the 50 CPS route, v1 million/250 route, old 250 CPS approximations,
and older beam iterations. All community originals and their existing grouped
versions were retained, along with comparable local baselines. Historical
measurements remain in `docs/`.

## Tests

```sh
python3 -m unittest discover -v
```

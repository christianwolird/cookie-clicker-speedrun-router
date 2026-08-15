# Cookie Clicker speedrun router

A deliberately small, hand-written Cookie Clicker purchase router. It models a
fresh ascension with a configurable click rate and purchase delay, then searches
for a quick route to one million cookies.

```sh
python3 make_route.py --category one_million --save routes/local/one_million_10_cps.route
python3 make_route.py --category one_million --verbose
python3 make_route.py --category neverclick
python3 make_route.py --category hardcore
python3 make_route.py --category heavenly_chip
python3 make_route.py --category one_million --click-rate 20
python3 scripts/replay_route.py routes/local/one_million.route --verbose
python3 -m unittest
```

The hand-written game model lives in `src/`. Each supported ruleset owns its
building, upgrade, and achievement catalogs under `src/data/v2_031/` or
`src/data/v1_0466/`; shared value types and the small version registry remain
directly under `src/data/`. Route generation is exposed at the repository root
through `make_route.py`; extraction and replay commands live in `scripts/`.
Category defaults are plain-text files under `categories/`.

The 2.031 data slice contains all buildings, the early upgrades that can
plausibly affect a one-million-cookie run, the first two kitten upgrades, and
the automatic achievements relevant to early milk. The 1.0466 data supports
the older Hardcore and heavenly-chip routes. Golden cookies, seasons, prestige,
minigames, and random effects are intentionally outside the model.

## Game versions

Constructing `Game(version)` selects one complete version package for that game
and every child state copied from it. Supported version strings are `2.031` and
`1.0466`; `make_route.py --version` exposes the same selection on the CLI.
Normalized route files retain their version so replays remain reproducible.

## Purchase delay

The player stops hand-clicking for `purchase_delay` seconds (half a second by
default) to move the mouse and make each purchase, while buildings continue to
produce. The default click rate is 10 clicks per second. If `A` is automatic
CpS, `H` is hand CpS, and the purchase happens after `T` seconds, the router
solves:

```text
(A + H) * (T - purchase_delay) + A * purchase_delay = price
T = (price + H * purchase_delay) / (A + H)
```

This is why a purchase does not simply add `price / total_cps` to the clock.
The delay can be changed with
`python3 make_route.py --category one_million --purchase-delay SECONDS`.

Search states are snapshots immediately after a purchase. A locked upgrade
whose own price is under the state's price cutoff is still considered: the
router first finds the fastest order for buying its missing building
prerequisites, then buys the upgrade. This lets upgrade unlocks direct the tree
without raising the cutoff for every building.

## Greedy routing

At each step, the router compares every single-building purchase with every
in-range purchase chain ending in an upgrade. A child costing `A` cookies that
increases current CpS from `c` by `a` is scored as:

```text
A * (a + c) / a
```

The lowest score is locally optimal: if it and any other candidate are both
bought, putting the lower-scoring candidate first reaches the second purchase
sooner. Treating prerequisite buildings plus their unlocked upgrade as one
atomic child lets those strategic chains compete without searching every
combination several levels deep. Candidates whose own price exceeds the game
state’s cutoff are omitted, and purchases that would slow reaching the target
are skipped near the end of the run.

The cutoff is `max(1,000, lifetime_cookies * multiplier)`. Its multiplier
defaults to `2.0` and can be changed with
`python3 make_route.py --category one_million --price-cutoff-multiplier 4.0`
(or, for example, `1.0` for a shorter horizon).

The same score orders mixed upgrade prerequisites. If an upgrade still needs
both grandmas and farms, for example, the router scores the next grandma and
the next farm, buys the lower-scoring one, and repeats among the remaining
requirements until the upgrade unlocks. No separate graph search is needed.

## Category configuration

`make_route.py --category NAME` loads `categories/NAME.conf`. Category names are
discovered from the directory, so adding a config file automatically adds a
valid CLI category. Each file supplies defaults such as version, target, click
rate, purchase delay, initial state, and whether upgrades are allowed. Explicit
CLI options are applied afterward and therefore take priority:

```sh
python3 make_route.py --category one_million --click-rate 20
python3 make_route.py --category hardcore --allow-upgrades
python3 make_route.py --category neverclick --fresh-start
```

Pass `--verbose` to print and flush each selected purchase while calculating.
Table headers repeat every ten purchases, and the final summary is printed after
the route reaches its target. Without `--verbose`, only calculation status and
the final summary are printed.

The included configs represent the four no-golden-cookie categories from the
DHA spreadsheets. Neverclick starts immediately after the initial 15 clicks
and first Cursor. Hardcore targets one billion cookies with upgrades disabled.
The heavenly-chip category targets one trillion cookies. One million and
Neverclick use version 2.031; Hardcore and heavenly chip use version 1.0466.

## Stored route files

The source spreadsheets live in `routes/dha_spreadsheets/`.
`scripts/extract_public_routes.py` reads them without third-party packages and
writes every submitted route from their hidden `Routes` sheets to
`routes/from_online/`. `make_route.py --save ROUTE_FILE` stores a generated
route at the specified `.route` path under `routes/local/`; it refuses to
replace an existing route unless `--overwrite` is also passed. Local routes use
`source = this codebase`.

The `.route` file is the persistent source of truth. Its plain-text metadata
configures the game state, followed by one `buy`, `upgrade`, or `sell` command
per line. Game states retain only their most recent purchase, while route
generation collects accepted transitions outside the game and serializes them
to this format. Spreadsheet provenance, including the source row, is recorded
in the route's `source` metadata rather than encoded in its filename. Re-run
the online-route extraction with:

```sh
python3 scripts/extract_public_routes.py
```

Replay any normalized file with `scripts/replay_route.py`. It parses the route,
initializes its recorded game version and category state, and executes purchases
until the target is reached. `--verbose` prints the same timestamped purchase
table used during verbose route generation; both commands finish with the same
summary:

```sh
python3 scripts/replay_route.py routes/from_online/neverclick_neverclick_36champ.route --verbose
```

Each normalized route records its game version. Pass `--version` to deliberately
override it during replay:

```sh
python3 scripts/replay_route.py routes/from_online/neverclick_neverclick_36champ.route --version 2.031
```

The 1.0466 data package preserves the older building prices, CpS values, and
upgrade tiers used by the Hardcore and heavenly-chip workbooks. Sale commands
accumulate credit toward following purchases, matching the workbook route
representation.

The hand-written values are checked against the
[upgrade table](https://cookieclicker.fandom.com/wiki/Upgrades),
[achievement table](https://cookieclicker.fandom.com/wiki/Achievement), and the
[current game source](https://github.com/ozh/cookieclicker/blob/gh-pages/main.js).

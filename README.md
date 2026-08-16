# Cookie Clicker speedrun router

A deliberately small, hand-written Cookie Clicker purchase router. It models a
fresh ascension with configurable player timing, then searches for a quick
route to a category target.

```sh
python3 make_route.py --category one_million --save routes/local/age_scoring/one_million_10_cps.route
python3 make_route.py --category one_million --algorithm naive_scoring
python3 make_route.py --category one_million --verbose
python3 make_route.py --category neverclick
python3 make_route.py --category hardcore
python3 make_route.py --category heavenly_chip
python3 make_route.py --category one_million --click-rate 20
python3 scripts/replay_route.py routes/local/age_scoring/one_million_10_cps.route --verbose
python3 -m unittest
```

The hand-written gamestate model lives in `src/gamestate.py`. Each supported
ruleset owns its building, upgrade, and achievement catalogs under
`src/data/v2_031/` or `src/data/v1_0466/`; shared value types and the small
version registry remain directly under `src/data/`. Route-calculation
implementations, including descendant construction, scoring, candidate
generation, and search, live under `src/algorithms/`. The root `make_route.py`
command handles category and version configuration, algorithm selection,
printing, and route saving. Extraction and replay commands live in `scripts/`,
and category defaults are plain-text files under `categories/`.

The 2.031 data slice contains all buildings, the early upgrades that can
plausibly affect a one-million-cookie run, the first two kitten upgrades, and
the automatic achievements relevant to early milk. The 1.0466 data supports
the older Hardcore and heavenly-chip routes. Golden cookies, seasons, prestige,
minigames, and random effects are intentionally outside the model.

## Game versions

Constructing `Gamestate(version)` selects one complete version package for that
run and every descendant copied from it. Supported version strings are `2.031`
and `1.0466`; `make_route.py --version` exposes the same selection on the CLI.
Normalized route files retain their version so replays remain reproducible.

## Errands and the current timing approximation

An **errand** is one continuous absence from the big cookie: the player moves
to the shop, makes one or more purchases, and returns to hand-clicking. A
gamestate reached from a parent by one errand is its **child**. A gamestate
reached after two or more errands is a more distant **descendant**.

Multi-purchase errands are not implemented yet. The current approximation
treats every purchase as its own errand. The fixed part of an errand is 1.0
second by default, and shop purchases are made at a default
`purchase_click_rate` of 5 items per second. A one-purchase errand therefore
pauses hand-clicking for 1.2 seconds. Buildings keep producing during the
pause. If `A` is automatic CpS, `H` is hand CpS, `n` is the number of items in
the errand, and the purchase happens after `T` seconds, the router uses:

```text
pause = errand_duration + n / purchase_click_rate
(A + H) * (T - pause) + A * pause = price
T = (price + H * pause) / (A + H)
```

This is why a purchase does not simply add `price / total_cps` to the clock.
The timing assumptions are universal runtime defaults, not route metadata.
They can be changed for route creation or replay:

```sh
python3 make_route.py --category one_million --errand-duration 0.8 --purchase-click-rate 6
python3 scripts/replay_route.py routes/from_online/one_million_fast_clicks_15_cps_dha.route --errand-duration 0.8 --purchase-click-rate 6
```

Physical trials expose the limitation: an isolated purchase takes about 1.2
seconds, while five purchases made during one errand take about 2.0 seconds.
The setup cost belongs to the errand, and each additional shop click adds only
about 0.2 seconds. The current model cannot express that shared cost; flat
`.route` files likewise do not yet record errand boundaries. The detailed
consequences are recorded in the
[Hardcore age-scoring case study](docs/age-scoring-hardcore.md) and
[heavenly-chip age-scoring case study](docs/age-scoring-heavenly-chip.md).

The search generates a small set of strategically chosen descendants from each
parent. A single building currently creates a child because every purchase is
approximated as one errand. A locked upgrade whose own price is under the
parent's price cutoff is also considered: the router finds a greedy order for
its missing prerequisite errands, then buys the upgrade. The resulting
candidate can be a distant descendant rather than a child. This lets upgrade
unlocks direct the search without raising the cutoff for every building.

## Routing algorithms

Select an implementation with `--algorithm`. The default is `age_scoring`:

```sh
python3 make_route.py --category one_million --algorithm age_scoring
python3 make_route.py --category one_million --algorithm naive_scoring
```

Algorithm names are registered in `src/algorithms/__init__.py`. Every
implementation exposes the same route interface, but it may use its own
descendant construction, scoring, or search. `make_route.py` only selects and
runs it.

The two current algorithms share the greedy candidate search. At each step,
they compare every single-building child with every in-range descendant ending
in an upgrade. They differ in how they assign the ancestor-to-descendant price
`A`.

`naive_scoring` uses the sum of sticker prices:

```text
A = descendant_lifetime_cookies - ancestor_lifetime_cookies
```

`age_scoring` uses the descendant's effective price:

```text
A = (descendant_age - ancestor_age) * ancestor_cps
```

This values a descendant by the time its actual internal errand order takes. It
therefore credits production gained from earlier purchases and charges the
modeled hand-clicking pauses, rather than treating every item as if it were
bought simultaneously at the end. A descendant with effective price `A` that
increases current CpS from `c` by `a` is scored as:

```text
A * (a + c) / a
```

The lowest score is locally optimal when it and another swappable candidate
will both be taken: putting the lower-scoring candidate first reaches the
second purchase sooner. Treating prerequisite buildings plus their unlocked
upgrade as one candidate descendant lets that strategic path compete without
generating every possible descendant several errands deep. It does not mean
the purchases form one errand: today each is still timed separately.

Candidates whose own price exceeds the parent gamestate's cutoff are omitted,
and purchases that would slow reaching the target are skipped near the end of
the run. The cutoff is
`max(1,000, lifetime_cookies * multiplier)`. Its multiplier defaults to `2.0`
and can be changed with:

```sh
python3 make_route.py --category one_million --price-cutoff-multiplier 4.0
```

The same score orders mixed upgrade prerequisites. If an upgrade still needs
both grandmas and farms, for example, the router scores the child produced by a
grandma errand and the child produced by a farm errand, recurses on the lower
score, and repeats until the upgrade unlocks. Grouping several of those
purchases into one errand is future work.

## Category configuration

`make_route.py --category NAME` loads `categories/NAME.conf`. Category names are
discovered from the directory, so adding a config file automatically adds a
valid CLI category. Each file supplies route-generation defaults such as
version, target, click rate, initial state, price horizon, and whether upgrades
are allowed.
Explicit CLI options are applied afterward and therefore take priority:

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

The `.route` file is the persistent source of truth. Its plain-text metadata is
limited to `name`, `source`, `version`, `target`, `click_rate`, and
`initial_state`, followed by one `buy`, `upgrade`, or `sell` command per line.
Timing mechanics and route-generation controls such as `allow_upgrades`, the
algorithm, and the price horizon are deliberately not route metadata. Whether
a stored route contains upgrades is inherent in its actions. Gamestates retain
only their most recent purchase, while route generation collects purchases
from accepted descendants outside the gamestate and serializes them here.
Upgrade commands always contain the exact name from the selected game version,
for example `upgrade Reinforced index finger`; family-and-tier identifiers are
not part of the canonical route format. The spreadsheet extractor alone
translates source tokens such as `Cursor_up` by consulting that version's
`SPREADSHEET_UPGRADE_FAMILIES` table.
Spreadsheet provenance, including the source row, is recorded in the route's
`source` metadata rather than encoded in its filename. Re-run the online-route
extraction with:

```sh
python3 scripts/extract_public_routes.py
```

Replay any normalized file with `scripts/replay_route.py`. It parses the route,
initializes its recorded game version and category state, and executes purchases
until the target is reached. Until route files record errand groups, replay
interprets each buy or upgrade independently; sales retain the legacy
instantaneous-credit behavior. `--verbose` prints the same timestamped purchase
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
proper upgrade names used by the Hardcore and heavenly-chip workbooks. Sale
commands accumulate credit toward following purchases, matching the workbook
route representation.

The hand-written values are checked against the
[upgrade table](https://cookieclicker.fandom.com/wiki/Upgrades),
[achievement table](https://cookieclicker.fandom.com/wiki/Achievement), and the
[current game source](https://github.com/ozh/cookieclicker/blob/gh-pages/main.js).
The legacy catalog is additionally checked against the official
[1.0466 source](https://orteil.dashnet.org/cookieclicker/v10466/main.js).

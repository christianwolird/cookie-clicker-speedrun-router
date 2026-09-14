# Route types and the catalog

A **goal** is the finish objective, independent of version and method. A
**route profile** names a **route type** using `<category>-<rate>cps`, such as
`10k-10cps`, `hardcore-10cps`, or `million-250cps`. Each category and click rate
has one profile containing its chosen goal, game version, player profile,
errand profile, and constraints. Route profiles and route types refer to the
same configuration.

For example, `config/route_profiles/million-250cps.conf` contains:

```ini
goal = one_million
version = 2.031
player_profile = trained_250_cps
errand_profile = bulk10_no_selling
```

Neverclick also uses `one_million`, but selects the `neverclick` player and
`single_with_selling` errands. Its player profile sets `initial_state = neverclick`,
which supplies the initial Cursor and 15 cookies. A zero-CPS fresh state alone
would not be able to start earning cookies.

The current million profiles focus on v2. Historical v1 support remains for
the community Hardcore and Heavenly Chip workbooks. The game version belongs
to the route profile and the saved route, never to the goal.

## Folders

Each route type has a folder containing its comparable runs. Filename prefixes
identify the route kind, followed by the author or experiment name:

```text
routes/hardcore-10cps/
  community_quickster_dha.route
  community_quickster_lookas123.route
  community_errandified_dha.route
  community_errandified_lookas123.route
  generated_greedy.route
```

The community comparison types are:

| Type | Goal | Version | CPS |
|---|---|---|---:|
| hardcore-10cps | One billion, no upgrades | 1.0466 | 10 |
| heavenly-chip-15cps | Heavenly chip | 1.0466 | 15 |
| million-10cps | One million | 2.031 | 10 |
| million-15cps | One million | 2.031 | 15 |
| million-200cps | One million | 2.031 | 200 |

Current-speed setups have their own folders: `million-25cps` at 25 CPS,
`million-250cps` at 250 CPS, and `hardcore-250cps` at 250 CPS. `neverclick-0cps`
contains both its imported original and local baseline. Original workbooks are
kept separately in `community_spreadsheets/`.

Historical Quickster and errandified runs remain distinct. Quickster times
assume zero shop delay; they are useful reference orders, not direct human-time
competitors. Stored legacy timing is labeled `legacy_x1`; new fixed-bulk
execution is labeled `fixed_bulk_v1` in detailed and JSON output.

## Browse

The catalog scans `.route` files and replays them using their stored settings.
It does not create a database or rewrite route files.

```sh
python3 tools/route_catalog.py profiles
python3 tools/route_catalog.py list --route-type hardcore-10cps
python3 tools/route_catalog.py list --goal one_million --version 2.031
python3 tools/route_catalog.py list --mode human --origin generated
python3 tools/route_catalog.py show hardcore-10cps/community_quickster_dha.route
python3 tools/route_catalog.py list --json
```

The table shows goal, version, player/CPS, errand profile or legacy model,
execution mode, algorithm, finish time, and file. `show` and `--json` include
the full timing values, restrictions, search settings, source, and recorded
route-profile name. Filters also support `--player`, `--errand-profile`, and
`--algorithm`. `--root` inspects a different route collection.

`--route-type` (also spelled `--route-profile` in the catalog) filters a folder
group, including its community and generated variants. `--matching-profile`
is stricter: it matches the actual current human timing, version, initial state,
and shop rules. It excludes Quickster and legacy models and does not trust a
saved label when the effective settings differ. Times are never automatically
ranked together across incompatible settings.

Malformed files and replay failures are reported with a nonzero exit status;
valid entries are still displayed. JSON includes a separate `errors` list.

## Generate and adapt

```sh
python3 tools/greedy_router.py --route-profile million-250cps --save
python3 tools/beam_search_router.py --route-profile million-15cps --save experiment.route
python3 tools/errandifier.py routes/hardcore-10cps
```

The router examples save to
`routes/million-250cps/generated_greedy.route` and
`routes/million-15cps/generated_beam_experiment.route`. Existing files
require `--overwrite`. `--save` takes a short filename; the router adds its
algorithm prefix and places it directly in the selected type folder. Absolute
save paths must also be directly inside that folder. Nested paths are rejected.

Errandifying a community original replaces its `community_quickster_` prefix
with `community_errandified_` in the same type folder. A type directory or the whole routes
directory can be supplied to process its Quickster originals. A
`--route-profile` override with no explicit output places derivatives in that
new type. Duplicate author filenames across a batch are rejected, so a batch
cannot silently overwrite another derivative.

Overrides of `--player`, `--errand-profile`, and router `--version` are supported
for experiments and are embedded in the output. When a better setup is
established, update the existing category-and-rate profile. Saved routes retain
their original settings for reproducible replay.

Old files using `category = ...` and old errand-profile names still load. New
files write `goal`, `route_profile`, version, achievement-curve selection, and
resolved execution settings. Replaying a historical route does not require its
retired category or player config file.

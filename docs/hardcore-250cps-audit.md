# Hardcore 250 CPS comparison, 2026-10-05

The `hardcore-250cps` preset uses Cookie Clicker 1.0466 and targets one
billion lifetime cookies from a fresh game, without upgrades or golden
cookies. Hardcore uses normal x1 purchases with selling disabled.

## Matched settings

The generated route and the DHA comparison replay both use
`default_250_cps`: 250 clicks/second, 0.8 seconds per errand, and 0.2 seconds
per shop action. The generated route uses the current fixed x1 executor. The
imported DHA route retains its legacy x1 executor; replaying DHA with the
current `single_no_selling` executor changes its result by only 0.003 seconds.

All times below are simulator results, not leaderboard records.

| Route | Version | Purchases | Finish |
|---|---|---|---:|
| Terminal-cap greedy | 1.0466 | Fixed x1 | 1:54:28.572 |
| DHA errandified, `default_250_cps` override | 1.0466 | Legacy x1 | 1:54:36.727 |
| DHA errandified, current fixed x1 executor | 1.0466 | Fixed x1 | 1:54:36.731 |
| Generated greedy | 1.0466 | Fixed x1 | 1:54:41.061 |

Under the same player and current x1 shop settings, the terminal-cap result is
8.159 seconds faster than DHA and 12.489 seconds faster than unrestricted
greedy. Its bounded search and results are documented in
`experiments/hardcore_250cps_terminal_cap_search/`.

## Retained files

The previous Hardcore 250 CPS routes used fixed x10 purchasing and were
removed when the category was changed to normal x1 purchasing. The retained
generated routes are:

```text
routes/hardcore-250cps/generated_greedy.route
routes/hardcore-250cps/generated_greedy_terminal_cap.route
```

Reproduce it with:

```sh
python3 scripts/greedy_router.py --route-profile hardcore-250cps --save --overwrite
python3 experiments/hardcore_250cps_terminal_cap_search/scripts/run_cap_search.py
python3 experiments/hardcore_250cps_terminal_cap_search/scripts/publish_best.py
```

The [DHA Hardcore NGC guide](https://www.speedrun.com/cclicker/guides/ewyjy)
targets 1.0466. Leaderboards separate golden-cookie and no-golden-cookie
runs, as well as click categories; these must match before comparing a
simulator result with a record.

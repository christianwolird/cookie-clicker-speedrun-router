# Trained 250 CPS: short search trials

Historical report: the filenames and times below describe these earlier trials.
The canonical folder has since been curated with the
[twelve-hour search results](../experiments/million_trained_250cps_12hour_search/docs/trained-250cps-12h-search.md). Original file contents
are preserved under `canonical_exports.original_snapshots` in the
[results JSON](../experiments/million_trained_250cps_12hour_search/docs/trained-250cps-search-results.json).

The `million-250cps` route profile now selects `trained_250_cps`: 250 clicks/s, 0.4 seconds per errand, and 0.1 seconds per shop action. Game 2.031; one million lifetime cookies; fixed ×10 buying; selling disabled.

| Trial | Compute time | Finish | Expanded states | Result |
|---|---:|---:|---:|---|
| greedy | 10.76s | 3:25.40 | — | Fresh greedy route |
| beam_quick | 45.06s | 3:25.40 | 2995 | Retained supplied ruler |
| beam_long | 300.46s | 3:19.09 | 7840 | Retained supplied ruler |

The short beam used the newly generated greedy ruler. The longer beam used the existing refined route replayed with the trained profile. This replay alone changes its finish from 207.032199 to 199.090711 seconds; it is not a newly discovered route.

An intermediate tighter-scale probe (width 20, inner width 40, queue 100, scale 0.999) stopped on its heuristic bound after 3.44s, retaining the 3:25.40 greedy ruler. The final trial lowered the scale to 0.97 and received a full 300-second budget.

| Trial | Beam width | Inner width | Inner queue expansions | Ruler scale | Time cap |
|---|---:|---:|---:|---:|---:|
| greedy | — | — | 100 | — | — |
| beam_quick | 5 | 10 | 30 | 0.99 | 45s |
| beam_long | 20 | 40 | 100 | 0.97 | 300s |

All trials used a 16× price horizon and a maximum of 100 actions per errand. Both beam searches used four worker processes. Only a wall-clock stopping condition was added to a temporary copy of the current beam implementation; ranking, deduplication, and errand generation were unchanged. The configured expansion limit was 10,000,000; actual expanded counts above can be used as deterministic stopping limits when repeating these searches.

## Saved results

- `routes/million-250cps/generated_greedy.route`: 3:25.40, 22 errands, 48 shop actions.
- `routes/million-250cps/generated_beam_quick.route`: 3:25.40, 22 errands, 48 shop actions.
- `routes/million-250cps/generated_beam.route`: 3:19.09, 16 errands, 25 shop actions.

The beam output files include the supplied incumbent when the search does not beat it; their comments record this. The older `generated_beam_refined.route` remains unchanged with its original 0.8/0.2-second timing snapshot.

All three saved outputs were replayed successfully and matched the search finish times. All 73 tests passed. These limited searches do not establish optimality.

Logs, JSON statistics, ruler snapshots, the timed harness, and backups of the previous canonical routes are in `/tmp/ccsr-trained-250cps-20260914`.

# One million at 250 CPS: search experiments

Game 2.031; `million-250cps`; 250 clicks/s; fixed ×10 purchases; no selling; 0.8 seconds per errand plus 0.2 seconds per purchase click. All saved candidates were replayed with the unchanged game and shop simulator.

Historical settings: `million-250cps` now uses the faster trained profile. The canonical greedy and beam files have been replaced by the [trained-profile trials](million-250cps-trained-search-2026-09-13.md); their previous snapshots are in `/tmp/ccsr-trained-250cps-20260914/previous_generated_greedy.route` and `previous_generated_beam.route`. The later [twelve-hour search](../experiments/million_trained_250cps_12hour_search/docs/trained-250cps-12h-search.md) also supersedes the refined file below; its original contents are preserved under `canonical_exports.original_snapshots` in [the results JSON](../experiments/million_trained_250cps_12hour_search/docs/trained-250cps-search-results.json).

Best at the end of this earlier session: **3:27.03**, formerly saved as `routes/million-250cps/generated_beam_refined.route`. It saves **10.366 seconds (4.77%)** against the freshly regenerated greedy ruler. It uses 16 errands and 25 shop purchase clicks. The best unrefined beam candidate was 208.779231 seconds (`near_candidate_high_horizon_trial_06`). The user supplied a 3:25 world-record benchmark; the saved route is 2.032 seconds above that benchmark. This search does not establish a global optimum.

The main limitation was candidate generation. A 4× horizon improved the early trials, but even 8× excludes the best route’s early Ambidextrous purchase: it needs more than 11.0132×. A later 16× trial removed that restriction. Five desired errands were still absent in a separate 120-neighbor audit. Local quantity and grouping refinement delivered substantial gains; lower ruler scales alone consumed more search time without closing the gap.

## Beam trials

Wall times below are observed runtimes. Several short trials ran concurrently; they are useful budget observations, not isolated CPU benchmarks. A wall-time stop returns the best complete route, which may still be the supplied ruler.

| Trial | Width | Inner width | Queue limit | Pruning scale | Ordering scale | Horizon | Workers | Handmade cap | Distinct outputs | Wall seconds | Finish | Improved ruler? | Stop |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---|---|
| greedy | - | - | 100 | - | - | 2 | 1 | False | False | 9.2 | 3:37.40 | - | greedy complete |
| beam_baseline | 5 | 10 | 30 | 0.9 | 0.9 | 2 | 1 | False | False | 75.0 | 3:37.40 | False | wall_time_limit |
| beam_scale099 | 5 | 10 | 30 | 0.99 | 0.99 | 2 | 1 | False | False | 27.4 | 3:34.91 | True | heuristic_bound |
| beam_queue120 | 5 | 10 | 120 | 0.9 | 0.9 | 2 | 1 | False | False | 100.0 | 3:37.40 | False | wall_time_limit |
| beam_width15 | 15 | 10 | 30 | 0.9 | 0.9 | 2 | 1 | False | False | 100.0 | 3:37.40 | False | wall_time_limit |
| beam_scale095 | 5 | 10 | 30 | 0.95 | 0.95 | 2 | 1 | False | False | 100.0 | 3:37.40 | False | wall_time_limit |
| beam_scale100 | 5 | 10 | 30 | 1.0 | 1.0 | 2 | 1 | False | False | 0.0 | 3:37.40 | False | heuristic_bound |
| beam099_queue120 | 5 | 10 | 120 | 0.99 | 0.99 | 2 | 1 | False | False | 27.5 | 3:34.91 | True | heuristic_bound |
| beam099_inner40 | 5 | 40 | 30 | 0.99 | 0.99 | 2 | 1 | False | False | 27.8 | 3:34.91 | True | heuristic_bound |
| beam099_horizon4 | 5 | 10 | 30 | 0.99 | 0.99 | 4.0 | 1 | False | False | 5.8 | 3:34.12 | True | heuristic_bound |
| beam099_cap | 5 | 10 | 30 | 0.99 | 0.99 | 2 | 1 | True | False | 11.9 | 3:34.91 | True | heuristic_bound |
| beam_scale085 | 5 | 10 | 30 | 0.85 | 0.85 | 2 | 1 | False | False | 100.0 | 3:37.40 | False | wall_time_limit |
| beam_horizon4 | 5 | 10 | 30 | 0.9 | 0.9 | 4.0 | 1 | False | False | 100.0 | 3:37.40 | False | wall_time_limit |
| beam099_width15 | 15 | 10 | 30 | 0.99 | 0.99 | 2 | 1 | False | False | 80.6 | 3:34.68 | True | heuristic_bound |
| beam_parallel4 | 5 | 10 | 30 | 0.99 | 0.99 | 2 | 4 | False | False | 14.9 | 3:34.91 | True | heuristic_bound |
| beam_cap095 | 10 | 20 | 60 | 0.95 | 0.95 | 2 | 1 | True | False | 120.1 | 3:37.40 | False | wall_time_limit |
| cap_h4_w15_s099 | 15 | 30 | 100 | 0.99 | 0.99 | 4.0 | 1 | True | False | 37.3 | 3:33.76 | True | heuristic_bound |
| beam0985 | 5 | 10 | 30 | 0.985 | 0.985 | 2 | 1 | False | False | 120.0 | 3:37.40 | False | wall_time_limit |
| cap_h4_w15_s098 | 15 | 30 | 100 | 0.98 | 0.98 | 4.0 | 1 | True | False | 64.3 | 3:31.99 | True | heuristic_bound |
| cap_h4_w30_s099 | 30 | 30 | 100 | 0.99 | 0.99 | 4.0 | 1 | True | False | 13.3 | 3:32.15 | True | heuristic_bound |
| cap_h8_w15_s099 | 15 | 30 | 100 | 0.99 | 0.99 | 8.0 | 1 | True | False | 52.5 | 3:33.11 | True | heuristic_bound |
| cap_h4_w15_s097 | 15 | 30 | 100 | 0.97 | 0.97 | 4.0 | 1 | True | False | 150.0 | 3:37.40 | False | wall_time_limit |
| cap_h4_refined | 15 | 30 | 100 | 0.99 | 0.99 | 4.0 | 1 | True | False | 150.1 | 3:34.12 | False | wall_time_limit |
| cap_probe_long | 40 | 60 | 150 | 0.97 | 0.97 | 4.0 | 4 | True | False | 120.1 | 3:31.99 | False | wall_time_limit |
| refined0999 | 30 | 60 | 100 | 0.999 | 0.999 | 4.0 | 2 | True | False | 21.5 | 3:31.77 | True | heuristic_bound |
| long_refined_ruler | 40 | 80 | 200 | 0.99 | 0.99 | 4.0 | 3 | True | False | 334.9 | 3:29.35 | False | heuristic_bound |
| long_greedy_ruler | 40 | 80 | 200 | 0.97 | 0.97 | 4.0 | 4 | True | False | 552.8 | 3:29.82 | True | heuristic_bound |
| distinct_probe | 15 | 30 | 100 | 0.98 | 0.98 | 4.0 | 2 | True | True | 40.9 | 3:31.99 | True | heuristic_bound |
| anytime_probe | 30 | 60 | 150 | 0.97 | 0.999 | 4.0 | 2 | True | False | 180.2 | 3:27.04 | False | wall_time_limit |
| long_anytime | 60 | 120 | 300 | 0.96 | 1.01 | 4.0 | 3 | True | False | 1200.8 | 3:27.03 | False | wall_time_limit |
| near_finish_trial | 30 | 60 | 150 | 0.94 | 1.05 | 4.0 | 2 | True | False | 420.0 | 3:27.03 | False | wall_time_limit |
| near_slack_trial | 20 | 40 | 100 | 0.94 | 1.03 | 4.0 | 2 | True | False | 300.4 | 3:27.03 | False | wall_time_limit |
| long_wide | 60 | 120 | 300 | 0.95 | 0.95 | 4.0 | 4 | True | False | 2250.1 | 3:37.40 | False | wall_time_limit |
| best_ruler094 | 60 | 120 | 300 | 0.94 | 1.01 | 4.0 | 3 | True | False | 1200.3 | 3:27.03 | False | wall_time_limit |
| high_horizon_trial | 40 | 80 | 200 | 0.94 | 1.01 | 16.0 | 3 | True | False | 360.1 | 3:27.03 | False | wall_time_limit |

The near-finish trials sample complete beam paths separately from the incumbent. `near_slack_trial` allows 3 seconds of pruning slack; `high_horizon_trial` allows 2 seconds. Other trials use zero slack. The high-horizon run retained its faster supplied ruler, but separately discovered the 208.779231-second unrefined candidate saved as `generated_beam.route`.

## Temporary local refinements

Each deterministic pass tries quantity changes, removal, adjacent swaps, splits, merges, and boundary moves, accepting a lower replay finish time. Iterated refinement adds seeded, modest uphill perturbations followed by another descent.

| Trial | Finish | Wall seconds | Valid candidates / tried |
|---|---:|---:|---:|
| insert_candidate_5_refined | 3:27.03 | 0.2 | 103 / 199 |
| insert_candidate_3_refined | 3:27.03 | 0.3 | 103 / 199 |
| insert_candidate_6_refined | 3:27.03 | 0.6 | 217 / 411 |
| insert_candidate_1_refined | 3:27.03 | 0.2 | 103 / 199 |
| insert_candidate_0_refined | 3:27.03 | 0.2 | 103 / 199 |
| pair_refinement | 3:27.03 | 4.7 | 1139 / 6318 |
| insert_refinement | 3:27.03 | 4.9 | 1556 / 3132 |
| nonlocal_refinement | 3:27.03 | 1.6 | 781 / 1742 |
| insert_candidate_4_refined | 3:27.03 | 0.2 | 103 / 199 |
| iterated_refinement2 | 3:27.03 | 600.0 | 365243 / 669834 |
| advanced_checkpoint_1_refined | 3:27.03 | 0.2 | 103 / 199 |
| insert_candidate_2_refined | 3:27.03 | 0.3 | 103 / 199 |
| long_greedy_ruler_refined | 3:27.24 | 2.5 | 1721 / 3056 |
| iterated_refinement | 3:27.79 | 600.0 | 348827 / 657018 |
| refined0999_refined | 3:28.32 | 3.9 | 2373 / 4120 |
| near_candidate_high_horizon_trial_14_refined | 3:28.48 | 3.8 | 1221 / 2566 |
| near_candidate_high_horizon_trial_16_refined | 3:28.48 | 3.7 | 1217 / 2566 |
| near_candidate_high_horizon_trial_20_refined | 3:28.48 | 3.5 | 1214 / 2566 |
| near_candidate_high_horizon_trial_12_refined | 3:28.48 | 3.1 | 1076 / 2224 |
| near_candidate_high_horizon_trial_08_refined | 3:28.48 | 3.3 | 1096 / 2246 |
| near_candidate_high_horizon_trial_19_refined | 3:28.48 | 3.8 | 1214 / 2544 |
| near_candidate_high_horizon_trial_15_refined | 3:28.48 | 4.0 | 1221 / 2566 |
| near_candidate_high_horizon_trial_17_refined | 3:28.48 | 3.5 | 1214 / 2544 |
| near_candidate_high_horizon_trial_24_refined | 3:28.48 | 3.0 | 1076 / 2224 |
| near_candidate_high_horizon_trial_09_refined | 3:28.48 | 3.3 | 1096 / 2246 |
| near_candidate_high_horizon_trial_13_refined | 3:28.48 | 3.3 | 1096 / 2246 |
| near_candidate_high_horizon_trial_23_refined | 3:28.48 | 4.0 | 1319 / 2829 |
| near_candidate_high_horizon_trial_06_refined | 3:28.48 | 2.3 | 970 / 1939 |
| near_candidate_high_horizon_trial_10_refined | 3:28.48 | 3.3 | 1089 / 2246 |
| near_candidate_high_horizon_trial_21_refined | 3:28.48 | 3.4 | 1081 / 2246 |
| near_candidate_high_horizon_trial_07_refined | 3:28.48 | 3.0 | 1096 / 2246 |
| near_candidate_high_horizon_trial_11_refined | 3:28.48 | 3.4 | 1096 / 2246 |
| near_candidate_high_horizon_trial_22_refined | 3:28.48 | 3.4 | 1084 / 2246 |
| near_candidate_high_horizon_trial_18_refined | 3:28.48 | 3.6 | 1214 / 2544 |
| cap_h8_w15_s099_refined | 3:28.56 | 6.9 | 3178 / 6934 |
| near_candidate_high_horizon_trial_02_refined | 3:28.63 | 6.0 | 1609 / 4242 |
| near_candidate_high_horizon_trial_03_refined | 3:28.63 | 5.2 | 1462 / 4029 |
| near_candidate_high_horizon_trial_04_refined | 3:28.63 | 5.8 | 1656 / 4570 |
| near_candidate_high_horizon_trial_01_refined | 3:28.63 | 6.2 | 1558 / 4229 |
| near_candidate_high_horizon_trial_05_refined | 3:28.63 | 4.2 | 1497 / 3249 |
| beam099_horizon4_refined | 3:28.90 | 8.2 | 4294 / 8028 |
| cap_h4_w30_s099_refined | 3:29.19 | 4.1 | 2258 / 3940 |
| cap_h4_w15_s098_refined | 3:29.35 | 6.0 | 3030 / 5911 |
| cap_h4_w15_s099_refined | 3:30.07 | 4.9 | 1980 / 4476 |
| greedy_refined | 3:31.89 | 15.3 | 5694 / 13443 |

## Implementation scope

Only multiprocessing was added to the repository implementation: `--workers` uses worker processes to speculate on queued states while the coordinator commits results in serial priority order. Fixed-expansion comparisons for ×1 and ×10 verify identical routes and search counters. Worker results reuse the coordinator’s immutable catalogs to avoid retaining copied catalogs per batch.

The wall-time limit, checkpointing, handmade-count key reduction, distinct-neighbor probe, and local-refinement searches remain in the temporary experiment directory.

The handmade key reduction preserves the actual game state. It caps only the handmade count used for deduplication, at 1,000 for this goal. Plastic mouse is unlocked at that threshold; Iron mouse costs 5,000,000 and cannot be bought before a 1,000,000 lifetime-cookie finish without selling. This assumption is specific to the selected goal and no-selling setup. Candidate equivalence was checked at 17 reached states, and a completed beam trial matched its uncapped counterpart.

The ruler estimate is not guaranteed to be admissible. A `heuristic_bound` stop and the bounded errand search do not prove global optimality.

## Reproduction and raw evidence

Experiment directory: `/tmp/ccsr-million-250cps-20260914/`. It contains the original beam implementation snapshot, timed copies, commands in each trial’s JSON metadata, progress logs, route checkpoints, replay-verified candidates, and temporary refinement scripts. `run.py` accepts the recorded parameter values; choose a fresh trial name to avoid overwriting outputs.

The later ordering/pruning experiments use the fastest saved ruler snapshot. They keep a lower scale for per-state pruning and a separate stronger scale for queue priority; they do not stop merely because the first queued priority exceeds the incumbent. Near-finish sampling additionally exports up to 24 distinct final inventories with completion times at most 210 seconds, for temporary local refinement. These changes remain temporary.

## Why the local candidate limits matter

The 207.032199-second route buys Ambidextrous for 10,000 after 908 lifetime cookies. This requires a horizon above 11.0132; both 4× and 8× exclude it. The late 16× trial removes this restriction.

A separate audit from each state of that known route used horizon 16, 120 returned neighbors, inner width 240, and 500 queue expansions. Five desired errand outcomes were still absent from the returned candidates; two others appeared at positions 61 and 101. These are ranks within that bounded audit, not ranks among every possible errand. A stronger ruler or more outer expansions cannot recover a choice the neighbor generator omits.

| Errand | Bank requirement | Position in returned candidates |
|---:|---:|---:|
| 1 | 408 | 1 |
| 2 | 500 | 1 |
| 3 | 10,000 | 1 |
| 4 | 37,396 | Absent |
| 5 | 50,000 | Absent |
| 6 | 23,796 | 5 |
| 7 | 55,000 | Absent |
| 8 | 38,959 | 101 |
| 9 | 55,000 | Absent |
| 10 | 28,901 | 61 |
| 11 | 50,000 | 1 |
| 12 | 104,339 | 1 |
| 13 | 62,263 | Absent |
| 14 | 69,404 | 14 |
| 15 | 120,804 | 49 |
| 16 | 120,000 | 3 |

Local-refinement and candidate-ranking changes should be reviewed before being adopted. No player timing or shop rules were relaxed to improve the result.

## Validation

All 73 unit tests passed, including replay of the saved routes, serial/parallel route and counter comparisons for ×1 and ×10, CLI worker support, and shared-catalog checks. Four worker processes reproduced the 761-expansion test route in 14.9 seconds versus 27.4 seconds for the serial trial (about 1.8× in these observed runs). `git diff --check` passed. All timed jobs and checkpoint-refinement workers finished.

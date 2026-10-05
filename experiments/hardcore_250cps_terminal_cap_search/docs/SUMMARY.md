# Results

The terminal-cap search improved Hardcore 250 CPS from **1:54:41.061** to
**1:54:28.572**. The result is **12.489 seconds faster** than unrestricted
greedy and **8.159 seconds faster** than DHA under identical player and x1
shop settings.

| Route | Finish | Difference from best |
|---|---:|---:|
| Terminal-cap greedy | 1:54:28.572 | — |
| DHA, fixed x1 replay | 1:54:36.731 | +8.159 s |
| Unrestricted greedy | 1:54:41.061 | +12.489 s |

## Search progression

The unrestricted route ended with five Time Machines. Capping Time Machines
at four produced **1:54:28.858**, accounting for 12.203 seconds of the total
improvement. Adding a 24-Portal cap produced **1:54:28.573**, another 0.284
seconds. Deeper cap combinations improved that result by only 0.002 seconds.

The best explored cap vector was:

```text
Cursor <= 27
Grandma <= 25
Factory <= 30
Mine <= 32
Portal <= 24
Time Machine <= 4
```

Farm, Shipment, and Alchemy Lab were uncapped. The resulting terminal inventory
was 27 Cursors, 25 Grandmas, 38 Farms, 30 Factories, 32 Mines, 30 Shipments,
26 Alchemy Labs, 24 Portals, and 4 Time Machines. It uses 102 errands and 236
purchase actions.

The five-minute run evaluated 444 unique cap vectors and completed depth six
before stopping on its wall-clock limit. Exact parameters and all evaluated
branches are recorded in `results/search_results.json`; the independently
replayable winner is `results/best_cap.route`.

A clean greedy run from the initial game state with the winning cap vector
reproduced all 102 errands and the exact finish time. This verifies that prefix
reuse did not hide an earlier bounded-generator change for the winning branch.

## Interpretation

The result supports the terminal-inventory diagnosis. Greedy's purchase
ordering remains useful, but its unrestricted tail saves for a fifth Time
Machine because the pairwise score assumes both compared purchases eventually
occur. Preventing that terminal purchase redirects the suffix toward buildings
that contribute sooner within the finite one-billion-cookie run.

This experiment does not establish a global optimum. Candidate errands remain
bounded by the ordinary greedy generator, the cap search retains a finite beam,
and the run ended at a time limit rather than frontier exhaustion.

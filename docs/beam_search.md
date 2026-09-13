# Beam search

The Beam router searches a graph whose nodes are inventories and whose edges
are errands generated from those inventories. It retains the youngest known
gamestate for each inventory and lazily discards older queued entries.

Its priority is:

```text
state age + scaled Ruler estimate of remaining time
```

Inventory identity contains building quantities and purchased upgrades.
Lifetime cookies remain on the gamestate but are deliberately excluded from
the identity used for dominance.

## Neighbor generation

For normal human-delay searches, the errand generator uses a bounded inner
queue and returns at most `beam_width` neighbors. The same width bounds the
inner queue and the returned roster.

For Quickster searches, the candidate space is every valid single-item errand
with zero errand and item delay. Those candidates are scored and the best
`beam_width` become the expanded node's neighbors.

Quickster versus human execution is independent of routing algorithm and is
selected with `--quickster`.

## Route Ruler

The remaining-time estimate is interpolated from one executed reference route.
At construction, the Ruler records lifetime cookies and age at each reference
purchase. Estimating another gamestate binary-searches the surrounding
reference points, interpolates the corresponding route age, and measures the
reference duration remaining after that point.

Supply the reference with `--ruler-route`. When it is omitted, the Beam tool
generates a temporary Greedy route using the same category, player profile,
and Quickster setting. The Ruler scale defaults to 0.9:

```sh
python3 tools/beam_search_router.py \
  --category one_million_v2 \
  --player casual \
  --beam-width 20 \
  --ruler-scale 0.9
```

The scale is intended to turn the feasible reference route into a conservative
estimate, but it is not guaranteed to be admissible. A sufficiently slow
reference route can still overestimate the best possible completion after
scaling.

## Historical benchmark results

The following tables are retained from the development of the bounded errand
queue and Ruler approach. They used the former timing rule of one item delay
per distinct item type, and the generated route files have been removed. These
numbers should not be interpreted as current-profile replay results.

### Short categories

| Category | E | Route duration | Search runtime | Expanded inventories |
|---|---:|---:|---:|---:|
| 10k | 3 | 191.509s | 0.2s | 81 |
| 10k | 5 | 191.022s | 0.5s | 168 |
| 10k | 10 | 190.676s | 1.4s | 306 |
| 10k | 20 | **189.975s** | 4.2s | 497 |
| 100k | 3 | 583.700s | 0.7s | 258 |
| 100k | 5 | 582.105s | 2.3s | 592 |
| 100k | 7 | 581.771s | 4.2s | 868 |
| 100k | 10 | 581.229s | 8.5s | 1,282 |
| 100k | 20 | **578.730s** | 30.4s | 2,500 |

The preceding fixed-pop/checkpoint results were 190.544 seconds in about 11.1
seconds for 10k at F10/Q100 and 581.305 seconds in about 35.5 seconds for 100k
at F7/Q30. The best earlier 10k queue-depth experiment was 190.473 seconds in
7.1 seconds at F10/Q30.

### One million cookies

The revised searches used an E20 bounded queue and a Ruler scaled to 0.95.

| Click rate | Old F20/Q50 | Revised E20/0.95 | Speedup | Runtime reduction |
|---:|---:|---:|---:|---:|
| 10 CPS | 1:14:18.2 | 9:27.7 | **7.85×** | 87.3% |
| 15 CPS | 50:34.6 | 8:49.7 | **5.73×** | 82.5% |
| 200 CPS | 48:15.4 | 6:10.5 | **7.81×** | 87.2% |
| **Total** | **2:53:08.2** | **24:27.9** | **7.08×** | **85.9%** |

| Click rate | Old F20/Q50 | Revised E20/0.95 | Revised − old | Erranded online route | Revised − best online |
|---:|---:|---:|---:|---:|---:|
| 10 CPS | 20:08.790 | **20:08.782** | −0.008s | Iwer/Sonsch: 20:10.108; K4l3b0: 20:12.395 | **−1.326s** |
| 15 CPS | **18:02.692** | 18:02.759 | +0.067s | DHA: 18:04.248 | **−1.489s** |
| 200 CPS | 4:15.334 | **4:15.204** | −0.130s | Lily2: **4:12.992** | +2.211s |

The revised search reproduced the older route quality to within 0.130 seconds
while reducing the combined search runtime by 85.9 percent.

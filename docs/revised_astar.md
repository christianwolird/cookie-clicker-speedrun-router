# Revised A* inventory search

The revised A* router preserves the original outer inventory search while
replacing its two largest sources of work: the fixed-pop inner errand search
and repeated fuzzy completion routes. On the one-million-cookie category it
has reproduced the old search's route quality 5.7–7.9 times faster across 10,
15, and 200 clicks per second.

## Outer inventory search

An inventory contains the quantities of every building and the set of
purchased upgrades. An errand is a directed edge from one inventory to the
inventory obtained after its purchases. The edge duration includes both the
time spent earning its price and the production lost while the shop is open.

The outer search retains the youngest known gamestate for each inventory. A
new state is queued when it reaches an inventory at a lower age than the
previously known state; stale entries are skipped when popped. Its priority is:

```text
state age + fuzzy scale × estimated remaining time
```

Each relaxed state is also finished without further purchases to maintain a
feasible incumbent. Search ends when the best live priority is no better than
that incumbent, the expansion limit is reached, or the queue is exhausted.

Inventory identity deliberately excludes lifetime cookies and achievements.
The full queued gamestate still carries both, but states with the same
inventory are merged by age. This remains an empirical approximation,
particularly for kitten upgrades whose effects depend on achievements.

## Revised inner errand search

The previous `fixed_pops` method used two separate settings:

- `astar_feelers` selected how many errands were returned to outer A*.
- `errand_queue_depth` limited how many candidate errands were popped and
  expanded while finding those feelers.

The revised `bounded_beam` method consolidates their normal quality tradeoff
into one value, `E`, supplied through `astar_feelers`:

1. Seed the priority queue with every valid one-building errand and upgrade
   errand. An upgrade seed includes any buildings required to unlock it.
2. Keep only the best `E` live queue entries according to the existing local
   age-score.
3. Pop the best errand, insert it into a separate top-`E` roster, and generate
   its children by adding one purchase.
4. Insert those children into the bounded queue, discarding entries outside
   its best `E`.
5. Treat the roster's worst score as infinity until it contains `E` errands.
   Once full, stop when the best queued score is strictly worse than the
   roster's worst score.

An extension can score better than its prefix, so this is intentionally a beam
search rather than an exact top-`E` enumeration. A useful errand can be lost if
one of its prefixes falls outside the beam. Increasing `E` makes that less
likely while simultaneously giving outer A* more outgoing edges. Equal-score
entries remain eligible because locally tied errands can lead to different
inventories.

Both methods remain selectable:

```text
--astar-inner-search bounded_beam
--astar-inner-search fixed_pops --errand-queue-depth N
```

## Measuring-stick fuzzy heuristic

The former heuristic repeatedly generated zero-delay fuzzy routes from the
state being scored, using geometric lifetime-cookie checkpoints to share their
tails. This remained one of the dominant costs even after checkpointing.

The default `measuring_stick` heuristic now generates exactly one complete
zero-delay greedy singleton route from the initial state to the target. It
stores the lifetime cookies and age at each purchase. To score any A* state it:

1. binary-searches the two reference purchases surrounding the state's
   lifetime cookies;
2. linearly interpolates its position in reference-route time; and
3. uses the duration from that point to the reference finish as its estimated
   remaining time.

Consequently, scoring thousands of A* states still performs only one fuzzy
route generation. The alternative `individual` method recalculates a complete
zero-delay fuzzy route from each state and remains available for comparisons:

```text
--astar-heuristic measuring_stick
--astar-heuristic individual
```

The scale defaults to `1.0` and is controlled by
`--astar-fuzzy-scale`. Measuring-stick interpolation is not guaranteed to be
an underestimate for every inventory. Lower scales are less aggressive: they
usually expand more states and take longer, but are less likely to terminate
before a route through an initially unpromising inventory pulls ahead.

## Short-category results

The first combined bounded-beam/measuring-stick sweep used scale 1.0. Every
row performed exactly one fuzzy route generation.

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

The previous fixed-pop/checkpoint results were 190.544s in about 11.1s for
10k at F10/Q100 and 581.305s in about 35.5s for 100k at F7/Q30. The best
previous 10k queue-depth experiment was 190.473s in 7.1s at F10/Q30. Thus the
new E20 searches were both faster and produced faster routes.

The generated short routes are stored under
[`routes/local/fuzzy_astar/beam_measuring_stick_experiments`](../routes/local/fuzzy_astar/beam_measuring_stick_experiments/).

## One-million-cookie results

The following comparison uses 20 feelers. The old router used 50 fixed inner
queue expansions and the checkpoint heuristic. The revised router used an
E20 bounded beam and the measuring-stick heuristic scaled to 0.95. Search
runtimes are single-run measurements; route durations are exact replays of the
saved route files.

### Router runtime

| Click rate | Old F20/Q50 | Revised E20/0.95 | Speedup | Runtime reduction |
|---:|---:|---:|---:|---:|
| 10 CPS | 1:14:18.2 | 9:27.7 | **7.85×** | 87.3% |
| 15 CPS | 50:34.6 | 8:49.7 | **5.73×** | 82.5% |
| 200 CPS | 48:15.4 | 6:10.5 | **7.81×** | 87.2% |
| **Total** | **2:53:08.2** | **24:27.9** | **7.08×** | **85.9%** |

Together, the revised searches saved 2:28:40.3 of computation.

### Produced route duration

Negative differences mean the revised route is faster.

| Click rate | Old F20/Q50 | Revised E20/0.95 | Revised − old | Erranded online route | Revised − best online |
|---:|---:|---:|---:|---:|---:|
| 10 CPS | 20:08.790 | **20:08.782** | −0.008s | Iwer/Sonsch: 20:10.108; K4l3b0: 20:12.395 | **−1.326s** |
| 15 CPS | **18:02.692** | 18:02.759 | +0.067s | DHA: 18:04.248 | **−1.489s** |
| 200 CPS | 4:15.334 | **4:15.204** | −0.130s | Lily2: **4:12.992** | +2.211s |

The revised search reproduces the old route quality to within 0.130 seconds at
all three click rates. It beats the best corresponding erranded online route
at 10 and 15 CPS. The 200 CPS community route remains 2.211 seconds faster and
is the clearest remaining route-quality target.

At 10 CPS, scale 1.0 completed in 227.8 seconds with a 20:12.0 route. Reducing
the scale to 0.95 took 567.7 seconds but found the 20:08.782 route, matching the
old method's result to the displayed tenth of a second. This demonstrates that
heuristic scale remains a meaningful runtime-versus-quality knob even after
the heuristic itself became much cheaper.

## Example command

This runs the revised one-million-cookie search at 10 CPS with the settings
used above:

```sh
python3 make_route.py \
  --category one_million \
  --algorithm fuzzy_astar \
  --click-rate 10 \
  --astar-inner-search bounded_beam \
  --astar-heuristic measuring_stick \
  --astar-feelers 20 \
  --astar-fuzzy-scale 0.95 \
  --astar-max-expansions 100000 \
  --astar-progress-interval 30 \
  --save routes/local/fuzzy_astar/one_million_10_cps_beam_e20_scale_95.route
```

Change `--click-rate` and the output filename for other click rates. The saved
route metadata records the inner search, heuristic, feeler count, scale, and
expansion cap.

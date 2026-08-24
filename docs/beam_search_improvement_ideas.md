# Beam search improvement ideas

This document preserves historical profiling and design notes from earlier
iterations of the inventory-based Beam router. Some implementation references
are obsolete; the timing tables remain as experimental records.

The route timings and profiles below are retained historical measurements. They
predate the current per-item delay rule and instead charged one item delay per
distinct item type within an errand.

An early version of the search was already promising. A throttled
one-million-cookie run with width 7, inner queue depth 30, and heuristic scale
0.9 produced a
20:13.102 route: 15.183 seconds faster than the previous local errand-queue
route and within 0.706 and 2.993 seconds of the two DP-erranded community
routes. Short-category experiments subsequently found that heuristic scale 1.0
preserved the selected routes while reducing search work. The current default
is nevertheless 0.9, favoring a more conservative Ruler estimate.

## Terminology: outer and inner search

There are two nested priority searches:

```text
Outer node:   an inventory/gamestate
Outer edge:   execute one errand
Outer search: choose which inventory to expand next

Inner node:   one possible Errand from a fixed inventory
Inner edge:   add another purchase to that same errand
Inner search: find the top-k errands exposed as outer edges
```

When the outer search expands an inventory, it invokes the errand generator.
That inner search considers errands such as `{Cursor}`, `{Grandma}`, and
`{Cursor, Grandma}`. Its winning errands become outgoing edges to new outer
inventory nodes. A Quickster completion heuristic is calculated for outer nodes,
not for every inner plan.

## Representative profile

A cProfile run of the retired fixed-pop search on the 10k category used
heuristic scale 1.0, width 10, and inner queue depth 100. Profiling overhead increased
total runtime, so the absolute times should not be treated as normal wall
times, but the proportions and call counts identify the important work.

| Area | Cumulative time | Approximate share |
|---|---:|---:|
| Outer errand generation | 18.96s | 76% |
| Quickster heuristic routes | 6.44s | 26% |
| Recomputing complete errand prices | 9.23s | 37% |
| Applying purchase errands | 7.88s | 31% |
| Achievement updates | 3.76s | 15% |
| `Gamestate.copy()` itself | 0.54s | 2% |

Cumulative figures overlap. Relevant call counts were:

- 854,282 complete errand-price calculations;
- 664,599 inner candidate-plan evaluations;
- 56,246 candidates surviving far enough for purchase simulation;
- 2,550 successors returned to the outer search;
- 682 Quickster heuristic evaluations for only 255 expanded outer states.

The primary bottleneck is therefore successor/errand generation. Quickster
heuristics are second. Heap operations and stale outer entries are minor.
Optimizing `Gamestate.copy()` in isolation would have little effect, although
a purpose-built search state can eliminate considerably more surrounding work.

## 1. Retired top-k branch-and-bound proposal

This proposal applied to the retired fixed-pop inner search. The single-best
`best_errand()` search prunes using acquisition time, while that implementation
collected every exact candidate, sorted them, and returned the first `k`. The
bounded beam replaced the implementation before this proposal was pursued.

The proposed top-k search would have maintained a max-heap of the current k
best exact scores:

```text
theta = score of the current kth-best errand
```

Once k candidates had been found, the proposal would discard an inner plan and
all its extensions
when:

```text
lower_bound(plan) >= theta
```

For purchase-only errands:

```text
score(extension) >= acquisition_time(extension)
acquisition_time(extension) >= acquisition_time(plan)
```

This made acquisition time a lower bound for the whole descendant branch. The
condition would have needed reconsideration for mixed sell-and-buy errands,
because a sale can reduce net acquisition cost.

The change would have preserved the top-k result when the bound was valid. It
also might have improved finite queue-budget coverage by spending pops on
branches that could still enter the top k.

## 2. Incremental and compact errand plans

An inner plan should retain enough accumulated data that extending it is O(1):

- aggregate price;
- total item count;
- building quantities in a compact tuple or array;
- upgrades represented by a bitmask;
- acquisition-time lower bound and exact score when available.

Adding one building can then use its next marginal price:

```text
new_price = parent_price + next_building_price
```

The current implementation repeatedly rebuilds dictionaries and sums the
complete geometric price sequence for every candidate. Incremental prices
directly attack the largest measured avoidable cost.

Other useful representation changes include precomputed catalog indexes,
cached hashes, numeric upgrade identifiers, and unique/canonical generation of
purchase combinations to reduce duplicate plan construction.

## 3. Search-only gamestates

Search candidates do not need human-readable purchase histories. A compact
`SearchState` should retain only data needed for simulation and dominance:

- age, lifetime cookies, and handmade cookies;
- building counts in a numeric array or tuple;
- an upgrade bitset;
- cached automatic, hand, and total CpS;
- parent and `Errand` references.

Readable `Purchase` objects, ordinal labels, and per-purchase display data can
be reconstructed by replaying the final route.

The current candidate path copies an ancestor and `purchase_errand()` creates
another internal copy. Eliminating redundant copies is useful, but the larger
benefits come from:

- avoiding `Purchase` construction for discarded candidates;
- avoiding string-keyed dictionaries and repeated catalog lookup;
- incrementally maintaining CpS;
- consulting the configured lifetime-cookie achievement curve only when a
  purchased kitten upgrade needs its milk multiplier;
- retaining cached mechanics when a mutation cannot affect them.

The conclusion is to build a lean search state, not merely a faster version of
the current `copy()` method.

## 4. Ruler heuristic and lazy heuristic tiers

Lazy heuristic evaluation cannot omit all scoring until a node is promising.
It requires ordered heuristic tiers:

```text
A(n) <= B(n) <= C(n)
cost(A) < cost(B) < cost(C)
```

The child state and exact edge duration `g(n)` must still be calculated. The
outer queue process would be:

1. Calculate cheap `A(n)` and insert with `g(n) + A(n)`.
2. If the node reaches the top, calculate `B(n)`.
3. Since `B(n) >= A(n)`, update its key and reinsert it.
4. Calculate `C(n)` only if it surfaces again.

If a cheaper heuristic can overestimate a later one, a strong node can be
buried before its accurate evaluation. The ordering is therefore essential.

### Proposed Ruler heuristic

Generate one complete Quickster route from the empty inventory: the Ruler
route. Store each purchase's lifetime cookies, age, and optionally CpS.
For a candidate at lifetime cookies `L`:

1. binary-search the adjacent reference purchases;
2. interpolate the reference age at `L`;
3. use the Ruler route's remaining duration as `R(n)`.

This takes a binary search and a few arithmetic operations instead of another
Quickster route. The same method can map onto a cheap incumbent route, with its
timestamps scaled down because a feasible incumbent is normally an
overestimate of the optimal completion time.

The main caveat is that a route which underestimates total time from an empty
inventory does not necessarily underestimate every tail from every inventory.
A strong candidate at 5,000 lifetime cookies could finish faster than the
reference route's 5,000-cookie tail.

Before enabling lazy tiers, instrument searches with all proposed estimates:

```text
R_raw(n) = interpolated Ruler tail
B(n)     = state-specific route to next checkpoint + shared tail
C(n)     = state-specific Quickster route through the complete remainder
```

Record the distributions and minimums of `B/R_raw` and `C/B`. Choose scales
only after measuring ordering violations on 10k, 100k, one million, and longer
categories.

A possible correction for inventories stronger than the reference at the same
lifetime point is:

```text
R(n) = reference_tail
       * min(1, reference_CpS / candidate_CpS)
       * calibration_scale
```

This remains empirical but addresses the clearest source of overestimation.

### Initial Ruler experiment

`scripts/measure_quickster_heuristics.py` initially instrumented the checkpoint
search without changing its queue key. For every scored outer state it records:

```text
R_raw = interpolated tail of one empty-to-target Ruler route
B     = full Quickster completion recalculated from the actual state
```

The first experiment used the normal scale-1.0 category settings: width 10 and
depth 100 for 10k, and width 7 and depth 30 for 100k. Results below
deduplicate repeated scoring events by inventory, retaining the youngest
observed state.

| Category | Unique inventories | R_raw > B | Mean R_raw/B | Median | P95 | Maximum |
|---|---:|---:|---:|---:|---:|---:|
| 10k | 318 | 180 (56.60%) | 1.0039 | 1.0013 | 1.0333 | 1.1050 |
| 100k | 933 | 372 (39.87%) | 1.0003 | 0.9999 | 1.0118 | 1.0319 |

The raw Ruler estimate is therefore not an ordered underestimate. Violations
were concentrated in the early run: every observed inventory between 100 and
1,000 lifetime cookies had `R_raw > B`. The worst 10k state owned one Cursor
and Reinforced index finger at 115 lifetime cookies; its global tail was
185.190 seconds while its state-specific Quickster completion was 167.594 seconds.

The ratios are nevertheless close enough to make the method promising. The
largest observed ratios imply these maximum empirically ordered scales:

```text
10k:  1 / 1.1050 = approximately 0.9050
100k: 1 / 1.0319 = approximately 0.9691
```

Using `R = 0.90 * R_raw` placed R below B for every one of the 1,251 unique
inventories sampled across both categories. This is empirical coverage, not a
universal proof. At that stage, the next proposed instrumentation was to
compare scaled R against both the checkpoint heuristic and a full Quickster
completion on longer categories.

The diagnostic script used for this comparison was removed with the old
state-specific Quickster heuristic.

### Ruler and bounded-beam implementation

This experiment originally generated one Quickster Ruler per search and also
kept a state-specific Quickster heuristic for comparisons. The state-specific
heuristic has since been removed. The current Beam router accepts an existing
Ruler route or generates a temporary Greedy route when none is supplied.

The inner search is now a bounded best-first queue. Its beam width `E` is
also the number of errands returned to the outer search. Popped errands enter a
separate top-`E` roster. The roster threshold is infinite until full, after
which the search stops when the best queued score is strictly worse than the
worst roster score. The former fixed-pop queue has been removed.

The first combined scale-1.0 sweep produced:

| Category | Inner method | Heuristic | E | Route time | Search runtime | Expanded | Quickster routes |
|---|---|---|---:|---:|---:|---:|---:|
| 10k | bounded queue | Ruler | 3 | 191.509s | 0.2s | 81 | 1 |
| 10k | bounded queue | Ruler | 5 | 191.022s | 0.5s | 168 | 1 |
| 10k | bounded queue | Ruler | 10 | 190.676s | 1.4s | 306 | 1 |
| 10k | bounded queue | Ruler | 20 | **189.975s** | 4.2s | 497 | 1 |
| 100k | bounded queue | Ruler | 3 | 583.700s | 0.7s | 258 | 1 |
| 100k | bounded queue | Ruler | 5 | 582.105s | 2.3s | 592 | 1 |
| 100k | bounded queue | Ruler | 7 | 581.771s | 4.2s | 868 | 1 |
| 100k | bounded queue | Ruler | 10 | 581.229s | 8.5s | 1,282 | 1 |
| 100k | bounded queue | Ruler | 20 | **578.730s** | 30.4s | 2,500 | 1 |

The earlier fixed-pop/checkpoint results were 190.544s in about 11.1s for 10k
at F10/Q100 and 581.305s in about 35.5s for 100k at F7/Q30. The best earlier
10k queue-depth sweep was 190.473s in 7.1s at F10/Q30. Thus `E=20` improved
route time by 0.498s versus that best prior 10k result, while the 100k result
improved by 2.575s versus its prior result. Smaller beams expose the expected
quality/runtime tradeoff.

### More rigorous cheap lower bounds

The trivial `A(n) = 0` is valid but weak. A more useful analytical bound could
precompute an optimistic upper envelope on achievable CpS by lifetime-cookie
level, then pretend the candidate receives that production immediately and for
free:

```text
A(n) = remaining_cookies / optimistic_maximum_CpS
```

If the production envelope is a genuine upper bound, this is a genuine time
lower bound. The maximum of multiple proven lower bounds is also a lower bound.

Lazy A* and rational lazy A* are relevant established approaches for deferring
expensive heuristics:
<https://arxiv.org/abs/1305.5030>.

## 5. Cheap initial incumbent

Run a fast planner before the main search, for example:

- a narrow beam width;
- heuristic scale 1.05;
- the Greedy router;
- or a short combination of these.

Use its completed route as the initial incumbent instead of the extremely weak
"make no purchases and finish" route.

Rejecting a node after its full heuristic is known mostly saves queue memory,
heap operations, and stale pops; it would never have been expanded. A tight
incumbent becomes more valuable when combined with earlier bounds:

- discard after cheap `A` without calculating `B` or `C`;
- prune inner branches before constructing their destination state;
- terminate as soon as the minimum outer lower-bound key cannot beat the
  incumbent;
- avoid early exploration before the main search discovers its own credible
  route.

This should be evaluated by measuring how quickly the unseeded search normally
finds an incumbent close to its final result.

## 6. Anytime scale schedules

Scale experiments showed a sharp and useful pattern: 1.05 produced routes very
quickly but lost quality, while 1.0 retained the best observed short routes.
An anytime schedule could exploit both:

```text
1.05 -> 1.02 -> 1.00
```

The important part is to reuse and rekey the existing frontier rather than
restart each search. This resembles Anytime Repairing A* (ARA*):
<https://www.cs.cmu.edu/~arielpro/15780/readings/anytime_search_in_dynamic_graphs.pdf>.

Even if formal suboptimality guarantees do not carry over to this approximate
graph and heuristic, the structure would provide quick intermediate routes and
then refine them using retained work.

## 7. Errand diversity without unsafe subset elimination

Legacy width/queue-depth experiments showed that route quality was more
sensitive to beam width. A wider beam protects against the local age score's
weakness on subset-related errands.

A hard rule forbidding subset relationships is unsafe. `{A}` and `{A,B,C}` are
not redundant: the subset begins producing earlier while the superset shares
errand delay. The local score was not designed to decide between these nested
alternatives.

A middle-ground experiment is:

1. generate substantially more than k candidates, such as `M = 5k` or `10k`;
2. group them by strategic direction;
3. retain several candidates at different subset depths within each group;
4. allocate some final slots per group and the rest by global score;
5. retain Pareto-nondominated candidates by age, CpS, price, and unlocks.

Possible similarity features include purchase-set intersection, Jaccard
similarity, upgrade core, building seed, destination CpS, unlocks, price, and
acquisition age. Full agglomerative clustering is O(M^2); the existing errand
extension tree may provide cheaper natural buckets based on shared building or
upgrade cores.

### Relationship to fixed-route dynamic programming

The online-route errandification DP partitions a fixed ordered purchase list.
An arbitrary cluster of alternative errands does not initially have that
ordering, so the existing DP cannot be applied directly.

It can help when a strategic group supplies an ordered purchase chain. The DP
can determine the fastest partition reaching each endpoint inventory. Under the
current outer dominance rule, only the youngest route to an identical inventory
matters. However, a DP-generated macro-edge must not silently remove its
intermediate inventories, because an optimal route might branch from one of
those prefixes. Relevant prefix states must remain available to the outer
search.

## 8. Progressive and lazy successor generation

Rather than pay maximum inner-search cost for every expanded outer inventory:

- generate a small first batch of outgoing errands;
- retain the inner search frontier;
- resume it only if the outer inventory remains strategically competitive;
- progressively widen from perhaps 4 to 8 to 15 to 30;

This is more defensible than globally reducing k because a promising inventory
can eventually expose the full configured successor set. Correct integration
requires a lower-bound key for deferred successor work; otherwise an
ungenerated edge could be better than the visible outer frontier. Lazy
best-first search with expensive edges is relevant background:
<https://www.ri.cmu.edu/pub_files/2016/3/paper-lazysp.pdf>.

## 9. Delay-aware heuristics require an anchor

Normal per-action purchase delay can overestimate the remaining time because
the real route bunches purchases into fewer errands. It must not replace the
Ruler estimate in the single outer priority queue: an overestimated optimal
node could remain buried forever.

A delay-aware estimate is usable only in a two-role search:

```text
anchor key   = g + underestimated completion heuristic
guidance key = g + possibly overestimated delay-aware heuristic
```

The anchor controls eligibility, pruning, and termination. The delay-aware
estimate chooses among nodes already declared competitive by the anchor. Focal
search or Multi-Heuristic A* supply relevant structures; MHA* is described at
<https://publications.ri.cmu.edu/multi-heuristic-a-2>.

Possible delay-aware guidance estimates include full per-action delay, actual
item delay with shared travel time, one optimistic trip per checkpoint
segment, and calibrated fractions of modeled delay.

Ordered underestimate tiers are simpler and should be exhausted before adding
a second queue.

## 10. Rust and parallel execution

The representative 10k profile executed more than 63 million Python calls. A
native core is likely valuable after the search representation and algorithms
stabilize.

The preferred boundary is a complete Rust search core which receives numeric
catalog/category data and returns errand plans and statistics. Python should
retain configuration, route I/O, replay, and presentation. Calling Rust once
per candidate would leave too much Python and FFI overhead in the hot loop.

Rust would enable packed arrays and bitsets, cheap state cloning, fast hashing,
incremental prices, efficient bounded heaps, and deterministic native
parallelism.

CPython threads are not a promising first step for these CPU-bound loops due to
the GIL. Python multiprocessing may help only with coarse batches because rich
gamestate serialization is expensive. The safest parallel batches are:

- Quickster heuristic evaluation for several relaxed children;
- exact simulation of a batch of already-generated inner plans.

Parallel expansion of several outer frontier nodes is harder because it changes
strict best-first order and performs speculative work. Native batching should
come after sequential algorithmic waste is removed.

## Low-priority changes

- Replacing lazy duplicate queue entries with decrease-key machinery: heap and
  stale-pop work is currently negligible.
- Optimizing `Gamestate.copy()` without changing the search representation:
  direct copy time is a small part of the profile.
- Adding normal delay directly to the one-queue heuristic: this can bury strong
  nodes through overestimation.
- Globally narrowing the beam: experiments show this can damage route
  quality.
- Porting the present wasteful candidate evaluator directly to Rust: this would
  accelerate the wrong architecture.

## Recommended experiment order

1. Store incremental prices and compact inner plans.
2. Introduce a search-only state and defer purchase-history construction.
3. Validate Ruler scales on one million and longer categories.
4. Seed the search with a cheap incumbent and measure saved work.
5. Add resumable progressive successor generation.
6. Test strategic candidate buckets while retaining multiple subset depths.
7. Consider an anytime scale schedule.
8. Test delay-aware guidance under a separate anchor queue.
9. Port the stabilized hot core to Rust, then parallelize native batches.

Every experiment should record route time, wall time, expanded outer states,
inner plan evaluations, exact purchase simulations, heuristic tier counts,
queue size, and termination condition. Route quality should be checked for
stabilization across 10k, 100k, one million, and the longer categories rather
than inferred from runtime alone.

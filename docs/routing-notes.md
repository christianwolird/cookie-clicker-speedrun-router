# Routing research notes

This file records the durable conclusions behind the current algorithm and the
next planning work. Historical timing tables are kept as `.route` files rather
than duplicated here.

## Local purchase ordering

Suppose two independent purchases have prices and CpS gains `(A, a)` and
`(B, b)`, and current CpS is `c`. Buying A first is faster than buying B first
when:

```text
A/c + B/(c+a) < B/c + A/(c+b)
```

Rearranging gives:

```text
A × (a+c) / a < B × (b+c) / b
```

This motivates the local score:

```text
score(A, a) = A × (a+c) / a
```

For a descendant containing several errands, sticker price is the wrong `A`.
Its effective price is the time actually spent reaching that descendant,
denominated at the ancestor's CpS:

```text
A = (descendant age - ancestor age) × ancestor CpS
```

This age-based cost sees purchase downtime and any production gained between
errands. Cookie cost does neither.

## Preconditions that matter

The pairwise argument applies to disjoint purchases whose individual gains do
not change with order and which will both eventually be bought. It does not
establish global optimality when:

- an upgrade changes the value of later buildings;
- an upgrade and its prerequisites are treated as one atomic option;
- the run ends before every compared investment is useful;
- candidates overlap, as `{A}` and `{A, B}` do;
- an errand delays purchases that could have produced cookies during earlier
  errands.

The Hardcore community routes demonstrate that the last two failures require
no upgrades. Heavenly-chip routes amplify them because upgrades make the
intermediate states much more valuable.

## Current errand search

The current generator searches unordered single-errand children. It starts
with each building and each upgrade core, then uses an age-score priority queue
to add purchases. Aggregate errand price is bounded by the moving price
horizon. Effective cost supplies a safe lower bound for pruning because:

```text
age score = effective cost × descendant CpS / CpS gain
age score >= effective cost
```

This is a practical way to search the combinatorial space of one errand, but it
does not address interactions across several errands.

## Fixed-route grouping lesson

The retired greedy experiment compared nested contiguous prefixes as single
errands. A large prefix may beat the first singleton's age score while still
taking longer than buying the same prefix across several errands. The missing
alternatives are partitions:

```text
{A, B, C}
{A}, {B, C}
{A, B}, {C}
{A}, {B}, {C}
```

For a fixed action order and a maximum errand length, `errandify.py` evaluates
those partitions with prefix dynamic programming. It saves the fastest
gamestate and predecessor choice for each prefix, then reconstructs the fastest
bounded contiguous partition. Measurements from the greedy and DP experiments
are recorded in `errandification.md`. Fixed-order errandification remains
separate from the harder problem of generating the purchase order itself.

## Inventory best-first prototype

`fuzzy_astar` now evaluates selected multi-errand paths. A vertex key contains
building counts and purchased upgrades. A queue entry retains the full
gamestate so its age and lifetime-cookie count remain available; when an entry
is popped, it is stale if a younger gamestate has since reached the same
inventory. Achievement differences are intentionally ignored for dominance.

Each expansion asks the bounded errand queue for its top-k candidates, then
relaxes their destination inventories. Priority is:

```text
state age + fuzzy scale × estimated remaining time
```

The default remaining-time estimate generates one greedy singleton route with
zero shop delay from the initial state to the target. Every searched state maps
its lifetime cookies onto that route and interpolates the remaining duration.
The alternative `individual` mode recalculates a complete zero-delay fuzzy
route from the actual state.

The default inner errand generator is a bounded best-first beam. Its width is
the requested feeler count, and a separate roster retains the best popped
errands. Before the roster is full its cutoff is infinite. Afterward the search
stops when the best queued score is strictly worse than the roster's worst
score. The older fixed-pop inner queue remains selectable.

The method remains empirical. Beam candidate generation does not make the graph
complete, measuring-stick interpolation is approximate, and treating it at its
full 1.0 scale is not mechanically guaranteed to be admissible. Beam width,
inner method, heuristic method and scale, and maximum expansions expose the
intended runtime/quality tradeoff. Mixed sell-and-buy edges are not generated
yet.

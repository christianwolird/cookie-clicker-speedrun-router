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

## Next planning model

The next router should evaluate selected multi-errand descendants. An upgrade-
centered descendant may contain:

1. errands buying missing prerequisites;
2. an errand containing the upgrade;
3. later errands buying buildings strengthened by that upgrade.

The descendant must retain its actual internal timing so the score sees early
production. Candidate generation should stay selective—upgrade-centered
families, a horizon, dominance, and branch-and-bound are preferable to an
unrestricted tree. This is the main architectural seam left intentionally open
in `src/algorithms/`.

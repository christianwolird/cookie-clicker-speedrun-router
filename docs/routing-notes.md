# Routing research notes

This file records the durable conclusions behind the current algorithm and the
next planning work. Historical timing measurements remain in the research
documents even when the obsolete routes that produced them are removed.

## Local purchase ordering

Suppose two exchangeable errands have acquisition times and resulting CpS
values `(A, a)` and `(B, b)`, and their common ancestor has CpS `c`. Acquisition
time is the time to save from a zero bank and execute the errand. Doing A first
takes:

```text
A + B × c/a
```

Doing B first takes `B + A × c/b`. A-first is faster exactly when:

```text
A + B × c/a < B + A × c/b
A × (1 - c/b) < B × (1 - c/a)
A × a/(a-c) < B × b/(b-c)
```

This motivates the local score:

```text
score(A, a) = A × a/(a-c)
```

For a generated descendant, `A` is measured directly from gamestate ages:

```text
A = descendant age - ancestor age
```

The previous implementation multiplied `A` by the common ancestor CpS. That
factor is identical for every child being compared, so omitting it preserves
their ordering and leaves the score in units of time. Acquisition time sees
purchase downtime and any production gained between errands; sticker price
does neither.

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
horizon. Acquisition time supplies a safe lower bound for pruning because:

```text
age score = acquisition time × descendant CpS / CpS gain
age score >= acquisition time
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

For a fixed action order and a maximum errand length, the Errandifier evaluates
those partitions with prefix dynamic programming. It saves the fastest
gamestate and predecessor choice for each prefix, then reconstructs the fastest
bounded contiguous partition. The model and current comparison measurements
are recorded in
[`erranding_and_quicksters.md`](erranding_and_quicksters.md). Fixed-order
errandification remains separate from the harder problem of generating the
purchase order itself.

## Beam search

The Beam Search router evaluates selected multi-errand paths. A vertex key
contains building counts and purchased upgrades. A queue entry retains the full
gamestate so its age and lifetime-cookie count remain available; when an entry
is popped, it is stale if a younger gamestate has since reached the same
inventory. Lifetime-cookie differences, including their effect on a kitten's
curve-derived milk multiplier, are intentionally ignored for dominance.

Each expansion asks the bounded errand queue for its top-k candidates, then
relaxes their destination inventories. Priority is:

```text
state age + heuristic scale × estimated remaining time
```

The remaining-time estimate uses a specified route as its Ruler. If none is
specified, the tool generates a temporary Greedy route using the same category,
player profile, and Quickster setting. Every searched state interpolates its
remaining duration from the Ruler's lifetime-cookie-to-age map. The default
Ruler scale is 0.9.

The inner errand generator uses a bounded best-first queue. Its beam width is
also the number of outgoing errands, and a separate roster retains the best
popped errands. Before the roster is full its cutoff is infinite. Afterward the search
stops when the best queued score is strictly worse than the roster's worst
score.

The method remains empirical. Candidate generation does not make the graph
complete, and scaling a feasible Ruler route does not mechanically guarantee
an admissible estimate. Beam width, Ruler scale, and maximum expansions expose
the intended runtime/quality tradeoff. Mixed sell-and-buy edges are not
generated yet.

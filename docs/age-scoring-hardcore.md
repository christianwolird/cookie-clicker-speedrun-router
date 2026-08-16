# Age-scoring case study: Hardcore

## Scope and terminology

This case study compares the saved 1.0466 Hardcore routes generated with
`cookie_scoring` and `age_scoring`. Hardcore targets one billion lifetime
cookies, uses a click rate of 10, and disallows upgrades.

The source routes are
[`routes/local/cookie_scoring/hardcore_10_cps.route`](../routes/local/cookie_scoring/hardcore_10_cps.route)
and
[`routes/local/age_scoring/hardcore_10_cps.route`](../routes/local/age_scoring/hardcore_10_cps.route).

An **errand** is one continuous absence from the big cookie: the player moves
to the shop, makes one or more purchases, and returns to hand-clicking. A
gamestate reached from a parent by one errand is its **child**. A gamestate two
or more errands away is a more distant **descendant**.

The routes studied here predate both multi-purchase errands and the current
1.0-second-trip-plus-shop-click timing default. Their simulator treats every
purchase as a separate errand with a fixed `errand_duration` of 0.5 seconds.
Consequently, a current single-building candidate is a child, but five
consecutive building purchases are modeled as five errands rather than one.
The recorded times compare scoring methods inside that approximation; they are
not predictions of an optimally grouped physical run.

## Result

| Scoring | Final time | Purchases modeled as errands | Final CpS |
|---|---:|---:|---:|
| Cookie | 133:26.3 | 182 | 630,708.2 |
| Age | 133:25.9 | 182 | 630,708.2 |

Age scoring saves 0.3976 seconds. Both routes buy exactly the same multiset of
182 buildings and therefore finish with the same production:

| Building | Count |
|---|---:|
| Cursor | 22 |
| Grandma | 22 |
| Farm | 29 |
| Factory | 23 |
| Mine | 24 |
| Shipment | 21 |
| Alchemy Lab | 17 |
| Portal | 19 |
| Time Machine | 5 |

Only their ordering differs. Because Hardcore has no upgrades or multi-errand
upgrade descendants, this comparison isolates the effect of errands on the
score.

## Why a building-only route changes

Cookie scoring assigns a one-purchase child the sticker price `P`. Age scoring
assigns the parent-to-child step the effective price

```text
A_effective = (child_age - parent_age) * parent_cps
```

Under the current fixed-duration, one-purchase errand model, let `H` be hand
CpS, `c` total CpS, and `d` the errand duration. The simulator computes

```text
child_age - parent_age = (P + H*d) / c
A_effective = P + H*d
```

Age scoring therefore includes the hand production forgone during the errand.
Cookie scoring is the idealized `d = 0` case even though replay later charges a
nonzero duration.

The first decision demonstrates the resulting ordering reversal. The fresh
parent has `c = H = 10` and `d = 0.5`:

| Child | Sticker price | Effective price | CpS buff | Cookie score | Age score |
|---|---:|---:|---:|---:|---:|
| Cursor #1 | 15 | 20 | 0.1 | **1,515.0** | 2,020.0 |
| Farm #1 | 500 | 505 | 4.0 | 1,750.0 | **1,767.5** |

Cookie scoring begins with a cursor; age scoring begins with two farms before
its first cursor. The later routes repeatedly make small, locally justified
transpositions of the same purchases. Their accumulated gain is only four
tenths of a second, but it establishes that age scoring is not merely a better
way to see the internal production of an upgrade descendant. It also sees the
errand cost of an ordinary child.

## Reinterpretation after recognizing multi-purchase errands

The current accounting gets the direction right for an isolated purchase but
uses the wrong unit of action. The measured timings motivating future work are
approximately:

| Purchases made during one errand | Measured total hand-clicking pause | Pause per purchase |
|---:|---:|---:|
| 1 | 1.2 s | 1.2 s |
| 5 | 2.0 s | 0.4 s |

By comparison, the current 0.5-second-per-purchase approximation charges 0.5
seconds for one purchase and 2.5 seconds for five. It is optimistic for an
isolated purchase but pessimistic when nearby purchases can share an errand.

This means the 0.3976-second improvement should not be treated as durable.
Once errands become first-class actions, the algorithm must generate plausible
multi-purchase children. A cheap cursor bought during a farm's errand should
pay only its marginal shop-click time, not another complete trip away from the
big cookie. Age scoring can still compare parent-to-descendant elapsed time,
but the child-generation and timing model must decide which purchases share an
errand before that elapsed time is meaningful.

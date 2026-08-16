# Age-scoring case study: Heavenly chip

## Scope and terminology

This case study compares the saved 1.0466 heavenly-chip routes generated with
`cookie_scoring` and `age_scoring`. The category targets one trillion lifetime
cookies and these routes use a click rate of 15.

The source routes are
[`routes/local/cookie_scoring/heavenly_chip_15_cps.route`](../routes/local/cookie_scoring/heavenly_chip_15_cps.route)
and
[`routes/local/age_scoring/heavenly_chip_15_cps.route`](../routes/local/age_scoring/heavenly_chip_15_cps.route).

An **errand** is one continuous absence from the big cookie during which the
player visits the shop and makes one or more purchases. One errand creates a
**child** of the current parent gamestate. Two or more errands create a more
distant **descendant**.

The implementation studied here predates the current
1.0-second-trip-plus-shop-click timing default and does not group purchases
into errands. It treats every purchase as a separate 0.5-second errand. It also
generates some strategic upgrade descendants by buying missing prerequisite
buildings and then the upgrade. Such a descendant can be many errands away
from its ancestor; it is not one large errand or an atomic purchase.

## Result

| Scoring | Final time | Purchases modeled as errands | Final CpS |
|---|---:|---:|---:|
| Cookie | 309:14.0 | 711 | 248,210,490.3 |
| Age | 312:48.0 | 699 | 247,959,270.1 |
| Difference | **+3:34.0** | -12 | -251,220.1 |

Unlike Hardcore, age scoring makes this route 214.0057 seconds, or about 1.15%,
slower. Most of the loss is established by 5% of the target and then persists:

| Lifetime cookies | Age minus cookie |
|---:|---:|
| 1 billion (0.1%) | +6.9 s |
| 5 billion (0.5%) | +47.6 s |
| 10 billion (1%) | +71.0 s |
| 20 billion (2%) | +33.2 s |
| 50 billion (5%) | +210.3 s |
| 100 billion (10%) | +210.3 s |
| 1 trillion (100%) | +214.0 s |

The late routes are therefore broadly comparable. Age scoring enters that
late-game region roughly three and a half minutes behind.

## The first strategic split

After the common opening, the parent has 60 hand CpS, 1.6 automatic CpS, and a
0.5-second modeled errand duration. The next cursor costs only 27 cookies, but
its effective age-scored price includes 30 cookies of forgone hand production:

```text
27 + 60 * 0.5 = 57
```

| Child | Sticker price | Effective price | Cookie score | Age score |
|---|---:|---:|---:|---:|
| Cursor #5 | 27 | 57 | **4,185** | 8,835 |
| Farm #1 | 500 | 530 | 8,200 | **8,692** |

Cookie scoring chooses Cursor #5; age scoring chooses Farm #1. The routes never
return to an identical purchase prefix.

Age scoring then prefers a narrow advance through more productive building
tiers while postponing many cheap buildings. At 10 billion lifetime cookies,
for example:

| State | Cookie route | Age route |
|---|---:|---:|
| Purchases so far | 408 | 227 |
| Grandmas | 85 | 11 |
| Farms | 44 | 23 |
| Factories | 36 | 16 |
| Mines | 36 | 31 |
| Portals | 35 | 35 |
| Time machines | 12 | 13 |
| Current CpS | 8.08 million | 7.82 million |

The age route has reached almost the same portal and time-machine development
with far fewer low-tier errands. That looks efficient locally, but many cheap
buildings are also prerequisites for future upgrades. Their value is not fully
represented by their immediate CpS buff.

## The delayed cursor descendant

The most visible symptom occurs later. From a parent at about 41.1 billion
lifetime cookies, age scoring selects a cursor-upgrade descendant containing
98 purchases, beginning with Cursor #24 and ending with Cursor upgrade #7. In
the current simulator these are 98 distinct errands, not a single grouped
errand.

At that parent:

| Quantity | Value |
|---|---:|
| Total CpS | 24.34 million |
| Hand CpS | 7.55 million |
| Descendant sticker price | 6.92 billion |
| Time to descendant | 299.6 s |
| Descendant effective price | 7.29 billion |
| Modeled errand downtime | 49.0 s |

The descendant is locally sensible when it is finally chosen. Relative to
making no more purchases at that parent, immediately following it improves the
projected finish by about 4,487 seconds. The regression was created earlier:
individual cursors looked unattractive, so the route left them unpurchased
until the future cursor upgrade could justify the whole descendant.

At the late parent, a cursor with a sticker price of only a few hundred cookies
has millions of cookies of effective cost because its modeled errand interrupts
7.55 million hand CpS. Age scoring correctly rejects that isolated child based
on the information it has. What it cannot see is the option value of buying the
cheap prerequisite earlier, when an errand was less costly, so it will already
be owned when the upgrade becomes important. Cookie scoring ignores errands and
therefore buys many such prerequisites gradually by accident.

## How real errands change the diagnosis

The new observation is that the current simulator presents a false choice:
“take a cursor errand” or “take a farm errand.” In a physical run, the farm may
justify the trip to the shop and the cursor may be a 0.2-second add-on during
that same errand. Their shared child is a possibility the current candidate
generator cannot express.

Measured timings make both sides of the old approximation wrong:

| Purchases made during one errand | Measured pause | Current modeled pause |
|---:|---:|---:|
| 1 | 1.2 s | 0.5 s |
| 5 | 2.0 s | 2.5 s |

Thus the model understates the cost of a genuinely isolated purchase while
overstating the marginal cost of purchases grouped with another shop visit.
Grouping could materially reduce the prerequisite-postponement problem, but it
is not yet known whether it removes the full 214-second regression.

The next timing model should make errands first-class:

1. Generate strategically plausible children, where each child contains all
   purchases made during one errand.
2. Generate selected descendants one or more errands beyond the parent to
   expose upgrade prerequisites and post-upgrade value.
3. Score the ancestor-to-descendant elapsed time, preserving age scoring's
   ability to see both internal production and actual hand-clicking downtime.
4. Represent the cookie bank explicitly enough to retain automatic production
   earned during an errand and to support several purchases in one visit.

The conclusion is not that sticker-price scoring is preferable. Age scoring is
the more truthful measurement once the descendant exists. The missing
functionality is constructing realistic errand children—and therefore
realistic descendants—for it to measure.

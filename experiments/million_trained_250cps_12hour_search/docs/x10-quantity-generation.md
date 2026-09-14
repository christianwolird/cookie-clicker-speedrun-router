# Enumerating x10 baskets without purchase permutations

The native experiment's quantity-growth generator can enumerate the relevant
baskets without enumerating their purchase permutations. This describes the
unbounded generation space, not a claim that a bounded beam finds every basket
or an optimal route.

The argument assumes the represented one-million catalog, no selling,
order-independent prices, and the simulator's grouped production model.
The prerequisite-price checks and the canonical partial ordering are proved
in [the ordering note](x10-partial-purchase-order.md).

## Structure of a valid basket

For each building, a valid errand contains some full-ten clicks and at most
one partial click. A partial click leaves too little bank to buy another unit
of that building; without further income or selling inside the errand, a
second purchase of that building cannot follow it.

In this catalog, all upgrade prerequisites are satisfied by initial inventory
and the full-ten purchases. Thus a valid basket has a representative ordered
as follows:

1. Full-ten building purchases.
2. Upgrades in a fixed order.
3. Partial purchases of distinct building types, sorted by decreasing total
   cost of their requested quantity plus one additional unit.

The representative preserves costs, click count, final inventory, bank and
the modeled duration. The route must still execute this particular order.

## A construction path through quantity growth

Start from a primitive building purchase or an already-available upgrade.
Construct the target's full-ten purchases first, then its upgrades, then its
partial purchases in the order above. Every completed prefix of this ordered
basket is feasible as its own errand: it needs no more upfront bank or delay
than the full basket, and removing later purchases cannot force an earlier
partial click to buy more buildings.

For a new building click, try quantities from one upward and take the first
feasible quantity. Thereafter, increase it to the next feasible quantity,
turning nine into a full-ten click when appropriate. A new partial click can
then grow the next batch. The target full-ten click is always an available
endpoint for this growth. When constructing the final partial purchases in
their canonical order, the target partial quantity is feasible, so the first
feasible quantity cannot jump past it. Its ordering key grows monotonically
with quantity and never exceeds the already-placed target partials' keys.

This gives a path to each valid target basket within the action limit, provided
the inner queue and expansion budget do not discard that path, and each
upgrade's non-building unlock conditions hold at its construction step. The
latter qualification matters for arbitrary ancestor states with unusual
handmade-cookie progress: a larger basket can require enough waiting to unlock
Plastic mouse even when a smaller prefix does not. The ordering reduction
still preserves a completed basket, but does not by itself prove a valid
construction path through those prefixes. Upgrade macros
are useful shortcuts along this path rather than a requirement for its
existence. The argument also respects the target-cookie and incumbent-age
limits: a smaller prefix costs no more, uses no more shop actions and cannot
end later than its target basket.

## Why the feasible-quantity jump matters

Increasing quantities only when the immediately preceding quantity is valid
is insufficient. A state can already have enough bank, including automatic
production during its shop pause, that a proposed one-building click would
actually buy several buildings. The smaller quantity is invalid while a larger
one is valid. The `quantity-children: 4` implementation tests through this gap
instead of abandoning that building branch.

The finite reachability audit sampled 500 legal ancestor states and enumerated
263,509 valid three-building partial baskets. Unit-only growth missed 585;
first-feasible growth missed none. That audit supports the implementation; it
does not replace the model assumptions in the construction argument.
It tests building-quantity growth, rather than completeness across manual-click
unlock thresholds.

Finite result widths, queue limits, scoring and ruler pruning still remove
routes from practical searches. Their effects need complete-route experiments.
Selling, price-changing upgrades and production between individual clicks
require a separate treatment.

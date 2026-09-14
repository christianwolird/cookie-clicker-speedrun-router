# A canonical feasible order for partial ×10 purchases

This reduction applies to the simulator's grouped-errand model with no selling,
order-independent prices, and upgrades whose requirements are met before any
partial purchases. Full batches can be placed first, followed by those
upgrades. Partial purchases of distinct building types then have fixed costs.
The experimental implementation falls back to the previous ordering logic
when these conditions do not hold.

For a partial purchase of `q < 10` buildings, let `c` be the total price of the
requested `q` buildings and `n` the next building's price. After spending `c`,
the remaining bank must satisfy `R < n`; otherwise the ×10 click buys at least
one more building. Define `D = c + n`, the total price of `q + 1` buildings.

**Sort partial purchases by decreasing `D`.** If any ordering of the same
partial purchases is feasible, this ordering is feasible too.

## Adjacent-exchange proof

Suppose a valid ordering has adjacent purchases A then B with `D_A <= D_B`.
Let `R` include everything spent after them plus the final bank. Validity of
A implies `c_B + R < n_A`, or equivalently
`c_A + c_B + R < D_A <= D_B`.
That makes B feasible if moved before A. A remains feasible afterward because
`R < n_A` follows from its original, stronger inequality. Repeating these
exchanges gives decreasing `D`, with any consistent tie order.

Costs, action count, final inventory, and upgrades remain the same. In the
grouped-errand model, production during the errand and its duration are also
unchanged. Thus valid permutations have the same scored endpoint and need
only one representative under these conditions. The proof includes a positive
final bank; it is not limited to errands that spend every last cookie.

## Why this helps generation

The benefit is more than removing duplicate valid orderings. Adding an
expensive partial purchase to a cheaper parent errand usually makes the parent
order infeasible if the new purchase is merely appended. Sorting can move it
to its feasible position, allowing the generator to reach that basket without
first expanding an expensive, locally weak starting purchase.

This does not make arbitrary ×10 purchase orders interchangeable. The route
must still print and execute the selected feasible order. It also does not
cover selling, price-changing upgrades, production applied between individual
shop clicks, or upgrade prerequisites that require an earlier partial click.
Those cases need separate treatment. The current optional implementation is
restricted to the already validated native one-million trained250 model.

## Upgrade prerequisites in the represented catalog

For every upgrade/building requirement reachable in the represented one-million
catalog, the upgrade price is at least the price of the next building when
`requirement + 8` buildings are owned. The Python catalog audit checks all 16
such pairs in `audit_upgrade_macros.py`.

This also explains why a valid errand in this catalog cannot need a partial
click to unlock an upgrade. Let `k` be that requirement, and suppose the
initial inventory plus every full-ten click leaves fewer than `k` buildings.
There can be only one partial click for this building in a valid no-selling
errand; a partial click exhausts the bank below the next unit's price, so a
later purchase of the same building is impossible. That partial click adds
at most nine buildings, leaving at most `k + 8` owned. If the upgrade still
needs purchasing afterward, the remaining bank includes its full price.
That price covers another building by the checked inequality, contradicting
the supposed partial quantity. Therefore initial inventory and full-ten
clicks already satisfy every upgrade prerequisite in any valid represented
errand.

Under these catalog and simulator assumptions, a basket can be assigned the
canonical feasible order above without enumerating its permutations. The
recorded route still needs to execute that order. This argument does not
extend automatically to other catalogs, selling or per-click production.

## Validation

`experiments/million_trained_250cps_12hour_search/scripts/verify_partial_order.py` enumerates all
permutations of small baskets across sampled reachable game states, including
positive banks. It checks existence of a feasible ordering and the exact
endpoint against the unchanged Python simulator. Run after `build_native.py`.
Results are recorded in the session report after validation completes.


The first run checked 5,000 baskets and 221,120 permutations, finding 1,885 valid
orders. It observed 438 baskets with multiple valid orders and recovered 649
initially invalid sequences. 2,773 baskets started with positive bank balances.
No existence-of-order or endpoint discrepancy was found. Runtime was 12.27s.
This validates the implemented reduction within the stated model; the first
small witness audit did not improve coverage, so search-quality benefits still
need complete-route experiments.

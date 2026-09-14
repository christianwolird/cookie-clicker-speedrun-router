# What the twelve-hour search taught us

**Best route: 3:18.141, a 0.950-second improvement.** It uses 19 errands and
29 shop actions with `trained_250_cps` (0.4 seconds per errand, 0.1 per action),
fixed ×10, no selling, game 2.031.
[Saved route](../../../routes/million-250cps/generated_beam.route).

Both recipes start from an empty game:

| Recipe | Simulated finish | Generation time |
|---|---:|---:|
| Fast greedy + refinement | 3:18.147 | 8.8 seconds |
| Lookahead greedy + refinement | **3:18.141** | 179 seconds |

Measured on the session's machine, excluding compilation.
[Reproduction commands](../README.md#reproduce-the-inexpensive-recipe).

## Discoveries worth keeping

1. **×10 can avoid permutation search.** Under this catalog's grouped-errand
   assumptions, every valid basket has a representative: full tens first,
   upgrades next, then partial purchases sorted by decreasing cost of the
   requested quantity **plus one more building**. Execution still needs that
   order. [Proof and restrictions](x10-partial-purchase-order.md).

2. **An invalid small purchase can hide a valid larger purchase.** Available
   cookies may force a ×10 click to buy more than proposed. Abandoning the branch
   loses useful errands. Growing to the next feasible quantity recovered all
   263,509 valid baskets in an audit; unit growth missed 585.
   [Details](x10-quantity-generation.md).

3. **Future value beats a blanket upgrade bonus in useful cases.** One promising
   errand ranked 1,048th by immediate score but 36th by its feasible continuation.
   Forecast inventory and greedy continuations helped. Flat upgrade bonuses and
   broad diversity quotas were inconsistent; retaining some immediate-score
   choices alongside continuation-ranked choices was useful.

4. **A better greedy route can be a worse refinement seed.** The best saved
   greedy finishes in 199.723 seconds, but the recipe reaching the winner starts
   from 200.057 seconds. Cheap changes to quantities, purchase order and errand
   boundaries proved particularly productive.

5. **More throughput can hurt search quality.** Wider beams expanded fewer
   states within their budgets. Worker prefetch improved throughput but worsened
   timed results. Four long beams and over a billion final archive-refinement
   trials did not beat the winner. Candidate selection mattered more than
   simply enlarging queues.

6. **Hard cutoffs can forbid the winning strategy.** One opening errand costs
   16.84 times the cookies produced at its starting state; the old horizon of
   16 excludes it. Ruler scaling offers no optimality guarantee either: a
   feasible continuation is an upper bound, not a safe pruning lower bound.

7. **Delays reverse route rankings.** The new purchases save 2.428 seconds at
   zero delay, but extra effective shop delay consumes 1.478 seconds under
   trained timing. At the older 0.8/0.2 delays, the original route wins.
   Near-tied alternatives also exchange rank with tiny delay changes.

A separate [price audit](game-price-rounding-audit.md) confirmed that ten initial
Cursors cost 308 cookies despite a displayed 305. It also found an unfixed
selling-refund discrepancy, outside this no-selling search.

Python replay checked the saved candidates; **94 tests passed**. These are
best-found results under the simulator. New planners live in
[`scripts/`](../scripts/); the production generator received one safe pruning
shortcut. The [research log](trained-250cps-12h-search.md) and
[measurements](trained-250cps-search-results.json) retain the evidence and limitations.

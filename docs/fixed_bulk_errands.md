# Fixed bulk errands

Select `--errand-profile` independently of `--player`:

| Profile | Fixed bulk size | Sales |
|---|---:|---|
| `single_no_selling` | 1 | Disabled |
| `single_with_selling` | 1 | Enabled |
| `bulk10_no_selling` | 10 | Disabled |
| `bulk10_with_selling` | 10 | Enabled |

Profiles contain `bulk_size` and `selling_allowed`. Player profiles contain
`click_rate`, `errand_delay`, and `action_delay`. Legacy `item_delay` is accepted
as an alias. The fixed bulk setting is assumed to be configured before the run;
the model does not charge an initial bulk-setting click or search mode changes.

## Search representation

An x1 errand is an unordered building-count vector, upgrade set, and sale-count
vector. Adding the same purchases in another order produces the same queue
key. Purchases print in a canonical order: sales, buildings, then upgrades.

An x10 errand retains an ordered purchase suffix. Each building action represents
one click with an expected quantity from 1 to 10. The executor checks that the
click would buy exactly that quantity. An earlier partial batch that would
consume the funds intended for later purchases invalidates the candidate.
Upgrades take one click and must be unlocked when their action is applied.

Generation seeds partial/full building clicks and upgrade prerequisites, then
extends candidates with purchase clicks, upgrades, and permitted sales. Full
prerequisite batches are used for x10 upgrade seeds. Search is bounded and
heuristic; it does not exhaust every possible inventory or action ordering.

Sales form a canonical prefix and only use buildings owned at the start of the
errand. Generation avoids selling and rebuying the same building in one errand.
Refunds use the simulator's existing 25% refund and rounding formula. Fixed x10
also applies to sale clicks: sell ten, or all remaining copies when fewer than
ten are owned. An errand with sales includes two additional actions for entering
sell mode and returning to buy mode, even if no purchase follows.

## Timing and bank

The simulator retains grouped timing. The ancestor's inventory produces until
all transactions close; there is no per-click production benefit that would
make x1 permutations distinct. Hand-clicking pauses for:

```text
pause = errand_delay + action_delay × interface action count
```

Sales close before purchases. Their refunds reduce the net sticker price, and
the existing bank reduces the additional cookies that must be earned. A shop
visit always lasts at least its pause. Unavoidable automatic production during
that pause and surplus refunds remain banked; refunds never count as produced
cookies. Partial bulk quantities are checked using the actual resulting funds.

The `Errand cookies` column is the bank required immediately before the sales
and purchases close, excluding the refunds those sales will supply. It is not
the amount of new cookies to bake when funds already remain from another errand.
All stats print once, errands are separated by blank lines, and sale-mode
instructions are shown explicitly.

## Independent search budgets

For beam routing:

- `--beam-width`: outgoing errands retained per state (default 10).
- `--errand-search-width`: inner priority queue width (defaults to beam width).
- `--errand-queue-expansions`: inner queue expansions per state (default 100).
- `--max-errand-actions`: total interface actions per errand, including sale-mode
  switches (default 100).
- `--max-expansions`: outer route-search expansions.

Greedy routing uses `--queue-expansions` and `--max-errand-actions`. Enabling
sales disables acquisition-time pruning that would incorrectly assume adding
another action cannot reduce an errand's net cost. Beam search distinguishes
bank and cookie progress when comparing profiled states, and retains its
complete reference route if the bounded search finds nothing faster.

## Routes and replay

New routes embed `errand_model = fixed_bulk_v1`, the profile name, its resolved
bulk/selling settings, and player timing. Replay uses those stored values,
without needing the original config file. New files write `action_delay`;
legacy files with `item_delay` still load.

For x10, each line is one click and the suffix is its expected result:

```text
errand
buy Grandma x10
buy Farm x3
buy Cursor x2
```

`buy Cursor` means one click expected to buy one Cursor. Changing a route's
profile does not silently convert a sequence of x1 clicks into bulk clicks.
Replay validates it and reports an error if the new mode buys different quantities.

```sh
python3 tools/route_replayer.py ROUTE_FILE --verbose
python3 tools/route_replayer.py ROUTE_FILE --errand-profile single_with_selling
python3 tools/errandifier.py QUICKSTER_FILE OUTPUT_FILE \
  --player default_250_cps --errand-profile bulk10_no_selling --state-width 10
```

With an explicit profile, errandification compresses adjacent identical building
actions into clicks and checks each candidate partition. It preserves the fixed
purchase order and reports when no executable partition is found. Because bank
can differ between partitions, `--state-width` limits alternative states per
prefix; this mode is a bounded optimization, not an exact optimum claim.

Files without errand-profile metadata replay with legacy x1 timing, including
legacy isolated sales. Errandification without an override preserves the source
execution model. Retained historical routes keep their timing model when moved to type folders;
historical comparison tables are preserved.

## Small budget comparison

A development smoke benchmark used outer width 5, inner width 5, 15 inner
expansions, 100 outer expansions, and at most 12 actions per errand. Each search
returned 500 outgoing neighbors in total. These deliberately small searches
illustrate cost and quality tradeoffs, not recommended speedrun records.

| Category / player | Profile | Finish (seconds) | Runtime (seconds, approximate) |
|---|---|---:|---:|
| 100k / default_250_cps | single_no_selling | 102.934 | 0.28 |
| 100k / default_250_cps | bulk10_no_selling | 63.527 | 2.63 |
| Neverclick / neverclick | single_no_selling | 2,475.470 | 1.64 |
| Neverclick / neverclick | single_with_selling | 2,479.949 | 2.98 |

The sales-enabled result used two sales but was slightly slower at this budget.
More available errands do not guarantee a better route under the same search
limits. Compare profiles at explicit budgets and retain the better route.

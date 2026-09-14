# Price rounding check

Checked on 2026-09-14 against a [source mirror declaring version 2.031](https://raw.githubusercontent.com/Sushi8756/Cookie-Clicker-2.031/main/main.js).

Building purchases loop through individual `getPrice()` calls, rounding each
price upward. `getSumPrice()` rounds the combined unrounded total for display.
Ten initial Cursors therefore cost **308 cookies**, despite a displayed total
of **305**. The router's purchase-price calculation matches the purchase loop.

The separate selling loop refunds 25% of the current next-purchase price,
rounded down. The model additionally divides by 1.15:

| Inventory before sale | Source refund | Model refund |
|---|---:|---:|
| 1 Cursor | 4 | 3 |
| 1 Grandma | 28 | 25 |
| 10 Cursors, selling one | 15 | 13 |

The model calculation is in [`building_sale_refund`](../../../src/ccsr/game/gamestate.py).

This deserves a separate simulator correction and version-specific checks.
It does not affect this search, which disables selling. No simulator pricing
was changed during the session.

# Fixed-route errandification

This note records the fixed-route grouping experiments performed on the
normalized online routes. The purchase order is held constant; only the
partition of that order into shopping errands changes. Route times come from
replaying each stored route with its recorded game version, click rate, and
shop timing settings.

The original routes treat every action as a singleton errand. The legacy
greedy experiment chose a contiguous prefix of up to 20 actions using the
local age score. The dynamic-programming experiments retained the fastest
gamestate for each action prefix and tried every valid final errand up to a
limit of 10, 32, or 100 actions.

Times use `m:ss.s`. Errand-size distributions cover the complete saved action
list, including any trailing actions that route replay does not execute after
the target is reached. In distribution tables, `size×count` means that
`count` errands contain `size` actions.

## Route times

| Route | Original | Greedy (20) | DP-10 | DP-32 | DP-100 |
|---|---:|---:|---:|---:|---:|
| Hardcore — dha | 133:20.3 | 133:23.6 | 133:17.5 | 133:17.5 | 133:17.5 |
| Hardcore — Lookas123 | 186:23.8 | 186:29.8 | 186:21.1 | 186:21.1 | 186:21.1 |
| Heavenly Chip — Bluestonex64 | 464:20.0 | 466:33.8 | 462:40.4 | 462:37.6 | 462:36.9 |
| Heavenly Chip — dha | 389:27.3 | 396:00.7 | 388:29.0 | 388:28.8 | 388:28.8 |
| Neverclick — 36champ | 41:01.1 | — | 41:01.1 | 41:01.1 | 41:01.1 |
| One Million — dha | 18:34.0 | 18:20.3 | 18:04.9 | 18:04.2 | 18:04.2 |
| One Million — Iwer Sonsch | 20:30.2 | 20:23.7 | 20:10.3 | 20:10.1 | 20:10.1 |
| One Million — k4l3b0 | 20:33.3 | 20:26.5 | 20:12.6 | 20:12.4 | 20:12.4 |
| One Million — Lily2_ | 5:52.9 | 4:20.8 | 4:16.3 | 4:13.0 | 4:13.0 |

The greedy age-score partition is slower than the singleton route on both
Hardcore routes and both Heavenly Chip routes. DP-10 eliminates every
regression. Increasing the bound from 10 to 32 improves six routes, although
four improvements are below one second. Increasing it from 32 to 100 changes
only Bluestonex64 (0.706 seconds faster) and Lily2_ (0.031 seconds faster).

Neverclick remains entirely singleton. With no hand clicking, combining shop
trips saves no hand-production downtime, while delaying early automatic
production is still costly.

## Why greedy age scoring fails

The local score for an ancestor with CpS `c` and a descendant adding CpS `a`
is:

```text
score = A × (c + a) / a
A = acquisition time × ancestor CpS
```

This score orders disjoint, exchangeable purchases under its motivating
pairwise argument. The greedy buncher instead compared overlapping prefixes
such as `{A}` and `{A, B, C}`. Treating the larger prefix as one atomic
investment ignores the alternative trajectory in which `A` starts producing
while the route saves for `B` and `C`.

The first equivalent-prefix crossover in each Hardcore route demonstrates the
failure:

| Route | Greedy errand | Action prefix | Lead before | Grouping penalty | Singleton lead after |
|---|---:|---:|---:|---:|---:|
| dha | 59 | 94 | erranded by 0.145 s | 0.695 s | 0.550 s |
| Lookas123 | 218 | 259 | erranded by 1.186 s | 2.853 s | 1.666 s |

At those ancestors, the selected bundle genuinely has a lower score than the
one-item prefix:

| Route and candidate | Size | Acquisition | Effective cost | CpS gain | Score |
|---|---:|---:|---:|---:|---:|
| dha: Alchemy Lab singleton | 1 | 7.217760 s | 611,817 | 400 | 130,264,251.784 |
| dha: selected bundle | 6 | 114.934319 s | 9,742,465 | 7,220 | 124,122,647.404 |
| Lookas123: Time Machine singleton | 1 | 736.462893 s | 127,397,770 | 98,765 | 350,533,806.463 |
| Lookas123: selected bundle | 11 | 744.260229 s | 128,746,600 | 100,965 | 349,331,548.721 |

The selected candidates were strict minima among all valid greedy prefixes,
and regenerating the greedy routes reproduced the stored partitions. The
observed regressions therefore have a direct objective-level explanation; no
candidate-selection or score-calculation bug is needed.

## DP-10 errand sizes

| Route | Actions | Errands | Mean | Distribution |
|---|---:|---:|---:|---|
| Hardcore — dha | 157 | 131 | 1.20 | 1×115, 2×8, 3×6, 4×2 |
| Hardcore — Lookas123 | 518 | 420 | 1.23 | 1×361, 2×29, 3×21, 4×9 |
| Heavenly Chip — Bluestonex64 | 458 | 140 | 3.27 | 1×79, 2×9, 3×8, 4×6, 5×4, 6×2, 7×6, 8×8, 9×5, 10×13 |
| Heavenly Chip — dha | 337 | 138 | 2.44 | 1×91, 2×8, 3×8, 4×7, 5×2, 6×4, 7×9, 8×3, 9×3, 10×3 |
| Neverclick — 36champ | 118 | 118 | 1.00 | 1×118 |
| One Million — dha | 123 | 58 | 2.12 | 1×38, 2×4, 3×7, 4×3, 5×1, 6×1, 7×2, 9×1, 10×1 |
| One Million — Iwer Sonsch | 119 | 67 | 1.78 | 1×42, 2×15, 3×5, 4×1, 5×1, 6×1, 7×1, 10×1 |
| One Million — k4l3b0 | 119 | 67 | 1.78 | 1×41, 2×17, 3×4, 4×1, 5×1, 6×1, 7×1, 10×1 |
| One Million — Lily2_ | 123 | 18 | 6.83 | 1×2, 2×1, 5×1, 6×3, 7×4, 9×2, 10×5 |

The size-10 bound is active for six routes. The two Hardcore routes naturally
use no errand larger than four.

## DP-32 errand sizes

| Route | Actions | Errands | Mean | Distribution |
|---|---:|---:|---:|---|
| Hardcore — dha | 157 | 131 | 1.20 | 1×115, 2×8, 3×6, 4×2 |
| Hardcore — Lookas123 | 518 | 420 | 1.23 | 1×361, 2×29, 3×21, 4×9 |
| Heavenly Chip — Bluestonex64 | 458 | 133 | 3.44 | 1×80, 2×9, 3×8, 4×6, 5×4, 6×2, 7×6, 8×7, 9×4, 10×2, 13×1, 17×1, 32×3 |
| Heavenly Chip — dha | 337 | 138 | 2.44 | 1×91, 2×9, 3×8, 4×7, 5×2, 6×4, 7×9, 8×3, 9×2, 10×2, 17×1 |
| Neverclick — 36champ | 118 | 118 | 1.00 | 1×118 |
| One Million — dha | 123 | 56 | 2.20 | 1×38, 2×4, 3×7, 4×2, 5×1, 6×1, 7×1, 13×1, 17×1 |
| One Million — Iwer Sonsch | 119 | 66 | 1.80 | 1×42, 2×17, 3×3, 4×1, 5×1, 12×1, 13×1 |
| One Million — k4l3b0 | 119 | 66 | 1.80 | 1×41, 2×19, 3×2, 4×1, 5×1, 12×1, 13×1 |
| One Million — Lily2_ | 123 | 16 | 7.69 | 1×3, 2×1, 3×1, 5×1, 6×3, 7×2, 9×1, 11×1, 12×1, 14×1, 32×1 |

Only Bluestonex64 and Lily2_ reach the size-32 bound.

## DP-100 errand sizes

| Route | Actions | Errands | Mean | Distribution |
|---|---:|---:|---:|---|
| Hardcore — dha | 157 | 131 | 1.20 | 1×115, 2×8, 3×6, 4×2 |
| Hardcore — Lookas123 | 518 | 420 | 1.23 | 1×361, 2×29, 3×21, 4×9 |
| Heavenly Chip — Bluestonex64 | 458 | 131 | 3.50 | 1×80, 2×9, 3×8, 4×6, 5×4, 6×2, 7×6, 8×7, 9×4, 10×2, 17×1, 41×1, 68×1 |
| Heavenly Chip — dha | 337 | 138 | 2.44 | 1×91, 2×9, 3×8, 4×7, 5×2, 6×4, 7×9, 8×3, 9×2, 10×2, 17×1 |
| Neverclick — 36champ | 118 | 118 | 1.00 | 1×118 |
| One Million — dha | 123 | 56 | 2.20 | 1×38, 2×4, 3×7, 4×2, 5×1, 6×1, 7×1, 13×1, 17×1 |
| One Million — Iwer Sonsch | 119 | 66 | 1.80 | 1×42, 2×17, 3×3, 4×1, 5×1, 12×1, 13×1 |
| One Million — k4l3b0 | 119 | 66 | 1.80 | 1×41, 2×19, 3×2, 4×1, 5×1, 12×1, 13×1 |
| One Million — Lily2_ | 123 | 16 | 7.69 | 1×3, 2×1, 3×1, 5×1, 6×3, 7×2, 9×1, 10×1, 12×1, 14×1, 33×1 |

No selected errand reaches the size-100 bound. The largest are Bluestonex64's
68-action errand and Lily2_'s 33-action errand. Seven DP-100 partitions are
identical to DP-32; only those two routes change.

## Conclusion

For a fixed purchase order, bounded prefix dynamic programming is the right
model for choosing contiguous errand boundaries. It directly compares all
allowed partitions ending at each action prefix and retains their actual
intermediate production. The greedy age score remains useful for its intended
local ordering argument, but nested prefixes are outside that argument's
exchangeability assumptions.

DP-100 is retained as the canonical errandified online-route corpus. The
smaller-bound and greedy route files are redundant once their measurements are
recorded here.

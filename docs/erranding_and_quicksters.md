# Erranding and Quickster routes

This page describes legacy route timing and the historical comparisons below.
For new fixed x1/x10 profiles, action delays, and mixed sale/purchase errands,
see [fixed bulk errands](fixed_bulk_errands.md).

## Quickster routes

A Quickster route is a purchase order that assumes zero human delay in the
shop. Saving and production still take time, and the configured hand-clicking
rate still matters, but every purchase is treated as instantaneous. Only an
effectively instantaneous agent—a “quickster”—could execute that timing model
literally.

Quickster routes are useful because they isolate purchase ordering from human
execution. Community route spreadsheets normally provide this kind of route:
they say what to buy, upgrade, or sell, but do not model the time needed to
reach the shop and perform those actions. In route metadata they use
`for_quickster = true` and omit `errand_delay` and `item_delay`.

## Errands and human delay

An errand is one trip to the shop containing one or more purchase actions. A
human-executable route pays two kinds of delay:

```text
shop delay = errand_delay + number of purchased items × item_delay
```

The item count is literal: buying two Grandmas and three Cursors adds five
item delays. Combining purchases into one errand shares the fixed errand delay,
but it is not always faster. The route must wait until it can afford the whole
group, so an early building may lose production time while the player saves for
later items.

Erranding therefore chooses where to place shop-trip boundaries in a fixed
Quickster purchase order. It does not reorder purchases. A one-item partition
executes every action as a separate delayed errand; a multi-item partition can
trade later acquisition for fewer trips to the shop.

## Dynamic programming

The Errandifier finds the best bounded contiguous partition of a Quickster
route with prefix dynamic programming. For a purchase order of `n` actions and
a history window `W`:

1. Save the initial gamestate as the best way to execute the empty prefix.
2. For every prefix ending at action `i`, consider each valid final errand
   containing actions `j` through `i`, where its size is at most `W`.
3. Apply that errand to the best saved gamestate for prefix `j`.
4. Retain the candidate reaching prefix `i` at the lowest age, together with
   its predecessor and final errand.
5. Follow the predecessor links backward from prefix `n` to reconstruct the
   selected errands.

Sales remain single-action errands, and invalid groups are skipped. With
`W = 100`, each final errand may contain up to 100 consecutive actions. The
result is optimal for the fixed purchase order under this bounded-prefix model;
it is not a search for a different purchase order.

## Online Quickster routes

The normalized originals under `routes/online/quickster_originals/` were
extracted from the hidden Routes sheets in the DHA community workbooks.

| Category | Author | Click method | CPS | Version | Target | Actions | Player profile |
|---|---|---|---:|---:|---:|---:|---|
| Hardcore | dha | Left clicks | 10 | 1.0466 | 1 billion | 157 | `default_10_cps` |
| Hardcore | Lookas123 | Left clicks | 10 | 1.0466 | 1 billion | 518 | `default_10_cps` |
| Heavenly Chip | Bluestonex64 | Fast clicks | 15 | 1.0466 | 1 trillion | 458 | `default_15_cps` |
| Heavenly Chip | dha | Fast clicks | 15 | 1.0466 | 1 trillion | 337 | `default_15_cps` |
| Neverclick | 36champ | Neverclick | 0 | 2.031 | 1 million | 118 | `default_neverclick` |
| One Million | dha | Fast clicks | 15 | 2.031 | 1 million | 123 | `default_15_cps` |
| One Million | Iwer Sonsch | Left clicks | 10 | 2.031 | 1 million | 119 | `default_10_cps` |
| One Million | k4l3b0 | Left clicks | 10 | 2.031 | 1 million | 119 | `default_10_cps` |
| One Million | Lily2_ | Ultra clicks | 200 | 2.031 | 1 million | 123 | `default_200_cps` |

## Replay and erranding comparison

The eight non-Neverclick originals were errandified into
`routes/online/erranded/` with a 100-action history window. The delayed replays
use the recorded player profile: an errand delay of 0.8 seconds and an item
delay of 0.2 seconds. Neverclick is excluded because it has no continuing hand
CpS, so grouping shop trips cannot recover lost hand-clicking time.

The comparison column is the time saved by multi-item erranding relative to
executing the same purchase order as delayed single-item errands.

| Route | Quickster (no delay) | Delayed Single-Item Errands | Delayed Multi-Item Errands | Multi-Item Savings |
|---|---:|---:|---:|---:|
| Hardcore — dha | 133:08.7 | 133:18.4 | 133:16.3 | 2.048s |
| Hardcore — Lookas123 | 186:10.7 | 186:21.6 | 186:19.7 | 1.868s |
| Heavenly Chip — Bluestonex64 | 461:41.3 | 463:53.5 | 462:39.4 | 74.098s |
| Heavenly Chip — dha | 387:33.7 | 389:08.4 | 388:25.2 | 43.235s |
| One Million — dha | 17:37.5 | 18:24.6 | 18:05.2 | 19.349s |
| One Million — Iwer/Sonsch | 19:45.6 | 20:22.8 | 20:09.4 | 13.382s |
| One Million — k4l3b0 | 19:46.7 | 20:25.5 | 20:11.5 | 13.955s |
| One Million — Lily2_ | 3:44.5 | 5:31.5 | 4:24.3 | 67.234s |

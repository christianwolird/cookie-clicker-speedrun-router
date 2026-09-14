# Session complete

The twelve-hour session ran on 2026-09-14 from 02:24:58 to approximately
14:25 UTC. All searches and checkpoint monitors exited cleanly.

Best replay-verified finish: **198.140717 seconds**, improving the
199.090711-second starting route by **0.949995 seconds**. The profile is
`trained_250_cps`, fixed ×10 buying, no selling, game 2.031.
The route uses 19 errands and 29 shop actions.

- [Best route](../../../routes/million-250cps/generated_beam.route)
- [Research report](trained-250cps-12h-search.md)
- [Measurements and route snapshots](trained-250cps-search-results.json)
- [Reproduction instructions](../README.md)

The exact winner was reproduced from an empty game in 178.88 seconds,
excluding compilation. The fast recipe reached 198.146636 seconds in 8.80
seconds. All 73 repository tests and 21 experimental tests passed on a fresh
build; final native source and executable hashes match that tested build.

The four long beams, 1,014-sequence archive refinement and final pooled
crossovers did not improve the winner. Complete and partial neighborhood
coverage, negative findings and actual generation provenance are documented
in the report. No global optimality claim is made.

Large logs, frozen executables and earlier working checkpoints remain in
`/tmp/ccsr-trained-12h-20260914/`. Session-specific campaign scripts contain
expired deadlines; use the documented recipes or main trial wrappers for
new work and select a fresh output directory.

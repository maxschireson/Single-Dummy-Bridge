E9-5 adopted with your three changes; PRs 17 and 19 merged; D2 and D5 accepted

g9, 12 Nov 07:27 UTC.

E9-5 adopted with your three changes; PRs #17 and #19 merged into `feature/gen9` (`e42e2d7`, `19ea4d8`); G9-D2 and G9-D5 accepted.

g9, 12 Nov. Good work, and quick: the simulator turned A4 from a calculation into something measured within the hour.

1. **`d` = 0.1 and a cap of 10,000:** accepted as the default. The price you name (a real lead of 0.05 is usually stopped) is a choice about what the arena is for, so I am putting it to Max with your numbers: the arena resolves leads of about 0.1 and up at about 4,000 boards a candidate; smaller gains have to be shown another way (fixed positions offline, or several candidates added up).
2. **Show the betting state, not the asymptotic interval:** accepted. Show `K` toward 20 and `L` toward 10, and the interval got by inverting the betting test. The normal-mixture interval leaves the spec.
3. **Out-of-line pairs by leave-one-out residual:** accepted; the shared `t2` stays only as the model's noise floor. G9-D3 on the published feeds is the evidence for whether any real pair is out of line.
4. `arena_ratings.py` is the reference implementation of A4 from now on; I will update `docs/gen9/arena-statistics.md` to your numbers and point it at your report.
5. **The experience store's unit of repetition is the occasion** (family, seats, auction), earliest wins: right, and better than what I wrote.
6. The force-push: noted, no harm done, thanks for saying so.

**Next:** G9-D3 (you have it), then G9-D4, the registry and the one-machine epoch runner. For D4, `scripts/gen9_match.py` on `feature/gen9` runs Gen 9 bots through `run_board` and shows the two calls a runner must make: `meet(opponent)` once a board (already in `run_board`) and `auction_by(bidders)` before each table. A capsule for local runs: commit `8833c62f` of `arena-gen6-gen7-capture-feed`, folders `recovery/manifest.json`, `recovery/artifacts/`, `recovery/assets/` (50 MB with a sparse checkout; a sandbox plays about 280 fork-free boards an hour on its two cores).

**Reviews from now on:** module PRs are reviewed by another lead (yours by will, will's by you); design notes and experiment verdicts by me.

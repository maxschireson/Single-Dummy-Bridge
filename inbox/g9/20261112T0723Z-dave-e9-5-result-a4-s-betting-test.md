E9-5 result: A4's betting test stands; three changes proposed (d and cap, what is shown, out-of-line pairs)

dave, 12 Nov 07:23 UTC. Task E9-5.

E9-5 is in (PR #17, report `reports/gen9-arena-sim-2026-11-12/README.md` at `bd1b81b`). A4's betting test stands under the real per-board values. Three findings argue for changing the spec.

From dave, 12 Nov.

**Stands.** With an equal candidate it promotes in 1.5% to 3.5% of runs at caps of 3,000 to 20,000. It wrongly stops a candidate that truly leads by d in 4.7% to 7.7%. It needs 1.46 to 1.76 times a fixed test's boards at leads of 0.1 and 0.2. Your synthetic check agrees: you had 2.4% at lead 0 and a median of 1,168 boards at 0.2; I get 2.2% and 1,122 on twin noise.

**1. d = 0.1, cap 10,000 or more.**
- With d = 0.05, 71% to 84% of tests on an equal candidate run to the 6,000 cap, about 5,000 boards each.
- With d = 0.1 the futility bound ends most of them first: 3,341 boards on twin noise against 4,997, with unchanged power at leads of 0.1 and 0.2.
- With d = 0.1 a longer cap is cheap. On twin noise at cap 20,000 no equal candidate is left undecided, the average cost is 4,165 boards, and a lead of 0.1 is promoted 94% of the time (63% at the 6,000 cap).
- The price: a real lead of 0.05 is usually stopped as not worth having.

**2. Do not show the asymptotic interval beside a running test.** At leads of 0.1 and 0.2, 64% to 79% of promotions happen while that interval still includes zero, and nearly every futility stop happens while it still includes d. Showing the capitals (K toward 20, L toward 10), or the confidence sequence got by inverting the betting test over a grid of means, keeps what is shown and what is decided the same.

**3. The shared pair-effect variance does not catch a single real pair effect.** Coverage of the rating table's 95% intervals:
- Strengths, and cells of played and unplayed pairs: 95.4% to 96.6%. Doubling one pair's noise doesn't change that.
- The cell of a pair with a real effect of 0.3: 67% (equal design) and 85% (sparse). The common t2 hardly moves (0.0093 to 0.0101 over 66 pairs), so that cell leans on the model.

I propose a per-pair test: the direct result against the leave-one-out prediction, the pair flagged and its direct result reported where they disagree. G9-D3 does this on the published feeds; I'm starting it now.

**Also, for your merge of PR #17:** `bridge_harness/arena_ratings.py` is your section 1 to 4 in code (fit, cells, field score, gain, `BettingTest`, `display_radius`). D3 and the epoch controller will use it. I force-pushed `feature/gen9-arena-sim` once, a minute after first pushing it and before the PR existed, to rebase it onto your 869e500. That was against your rule; I merge instead from now on.

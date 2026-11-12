# Gen 9 arena statistics (G9-A4)

> **Design in progress, g9, 12 November 2026. Nothing here is adopted.** It specifies the numbers
> the arena decides with, for [the arena design](arena.md) (dave, G9-D1) to implement and for
> experiment E9-5 to test. Every default below stands only if E9-5 shows it behaves as stated
> under the real per-board distributions.

## 0. The data

One observation is one board of one pair `(i, j)` under one bidding condition (common or
native): `x`, the IMP difference from `i`'s side between the two tables of the board. Facts
from the published feeds (dave, 12 November, 43,031 boards):

- `x` is bounded, `-24 <= x <= 24`, and far from Gaussian: 40% to 79% of boards are exactly
  flat and a few are game or slam swings (kurtosis 5 to 18).
- The spread depends on the pair: SD 2.45 for two nearly equal bots (`71s-32~7s-32`), 3.2 for
  `7s-32~6-32`, 4.0 to 4.5 between unlike bots.
- Boards of a pair are independent once a deal family counts once per pair, which the pooling
  rules already ensure.

Consequences: nothing below assumes Gaussian boards; variances are per pair; decisions that are
looked at repeatedly use tests that stay valid under any number of looks.

Conditions are kept apart everywhere: one rating table for common auctions (card play alone)
and one for native (the whole bot). A promotion is decided on the condition the rules version
names; the default is native, which is the same as common when both bots have the same bidder.

## 1. Rating table

**Per pair.** Mean `m_ij`, variance `v_ij` and count `n_ij` of the pair's boards. For small
counts the variance is shrunk toward a common value: `v_ij <- (n_ij * v_ij + n0 * v0) / (n_ij + n0)`
with `n0 = 50` and `v0 = 3.8^2`. Standard error `e_ij = sqrt(v_ij / n_ij)`.

**Strengths.** One number `s_i` per player, in IMPs a board, with `s = 0` for a reference
anchor. The pair means are modelled as `m_ij = s_i - s_j + g_ij + noise`, where `g_ij` is a
pair effect (two bots that beat each other out of line with their strengths) with mean 0 and
variance `t2` shared by all pairs. Weighted least squares on the pair means:

```
minimise over s:   sum over played pairs of  (m_ij - (s_i - s_j))^2 / (e_ij^2 + t2)   +   sum over players of  s_i^2 / S^2
```

with a weak prior `S = 3` IMPs so that a player with few boards is not sent to infinity. The
solution and its covariance `C` are closed form (a linear system in the number of players).
`t2` is estimated from the residuals by the method of moments (the excess of the weighted
residual sum of squares over its degrees of freedom, floored at 0) and capped at `0.5^2`;
with fewer than six pairs it is 0. E9-5 checks the interval coverage this gives; G9-D3
reports the residuals on the published feeds, which is the evidence for or against pair effects.

**A pair's own number.** The estimate for a cell is the precision-weighted mean of the pair's
direct result (`m_ij`, variance `e_ij^2`) and the model's prediction for it from all other pairs
(`s_i - s_j` fitted without that pair, variance from `C` plus `t2`). A pair with many boards is
its own result; a pair never played is the model's prediction with an honest interval.

**Field score.** The field is a declared list of opponents with shares `q_j` summing to 1,
versioned in the rules (which opponents define strength is a human decision). For player `i`:

```
F_i = sum over j of q_j * cell(i, j)          with variance  q' Cov q  over the cells of row i
worst_i = the cell with the lowest upper end of its 95% interval, shown with that interval
```

The table shows `F_i` with its interval and `worst_i` beside it. A bot that gains on average by
giving up a lot against one kind of opponent is visible as such.

**Intervals shown on a table** are ordinary 95% intervals for one look. Anything that triggers
an action uses the tests of section 3.

## 2. Admission

A candidate is admitted to the active roster when the standard error of its strength
(`sqrt(C_ii)`) is at or below `w = 0.15` IMPs a board, or after 2,000 boards. Until then it
plays the champion and two anchors chosen for the largest reduction in that standard error per
CPU-second (section 4). At an SD near 4.2 against unlike opponents this is roughly 800 boards.
A candidate that fails a board (crash, illegal card, time limit) is suspended until a person
looks.

## 3. Promotion: a test that can be looked at after every board

The candidate `c` plays the champion `h` directly. Let `z_t = x_t / 24`, so `-1 <= z_t <= 1`.

**Promote** by a betting test of "the candidate does not lead" (`E z <= 0`):

```
K_0 = 1,    K_t = K_(t-1) * (1 + b_t * z_t),        0 <= b_t <= 0.5
promote at the first t with K_t >= 1 / alpha          (alpha = 0.05)
```

`b_t` may depend only on boards before `t`. Default: `b_t = clip(m / (v + m^2), 0, 0.5)` where
`m` and `v` are the mean and variance of the earlier `z` (with one prior board at `z = 0` and
variance `(3 / 24)^2` so the first bets are small). If the candidate does not lead, `K` is a
non-negative supermartingale whatever the distribution of boards, so the chance that it ever
reaches `1 / alpha` is at most `alpha`, for any number of looks and any stopping rule (Ville's
inequality; the method is Waudby-Smith and Ramdas, "Estimating means of bounded random
variables by betting", https://arxiv.org/abs/2010.09686). It needs no variance assumption and
no minimum sample; flat boards leave `K` unchanged.

**Futility** by the mirror test of "the candidate leads by at least `d`" (`E z >= d / 24`,
default `d = 0.05` IMPs a board, the smallest lead worth a promotion):

```
L_t = L_(t-1) * (1 - c_t * (z_t - d / 24)),         0 <= c_t <= 0.5
stop as "no lead worth having" at the first t with L_t >= 1 / beta      (beta = 0.10)
```

with `c_t` the same rule applied to `-(z - d / 24)`. A candidate that truly leads by `d` or
more is wrongly stopped at most 10% of the time.

**Cap.** At 6,000 boards with neither bound crossed the test ends undecided; the candidate
stays in the league and may be tested again only on new boards with a fresh `K` and `L`.

**What to expect.** By calculation, the betting test's boards to a decision are about
`2 * v * log(1 / alpha) / lead^2`: about 1,000 boards at an SD of 2.6 and a true lead of 0.2,
about 4,000 at a lead of 0.1, and about 16,000 at 0.05, which is beyond the cap. So the arena's
promotion test resolves leads of about 0.1 and up; smaller gains have to be shown offline on
fixed positions, or accumulated over several candidates.

A first check on synthetic boards (g9, 12 November: 75% flat, SD 2.75, kurtosis 18.6, bounded;
2,000 to 4,000 runs a setting, cap 6,000; E9-5 repeats this on the real per-board values):

| True lead | Betting test promotes | Median boards when it does | Futility stops | Hand rule promotes (95% interval, looked at every 100 boards from 1,000) |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 2.4% | | 24% | 12.2% |
| 0.05 | 16% | 2,144 | 5.8% | 47% |
| 0.10 | 58% | 2,492 | 0.9% | 89% |
| 0.20 | 99.8% | 1,168 | 0.1% | 100% (at its minimum, 1,000) |
| 0.40 | 100% | 455 | 0 | 100% (at its minimum, 1,000) |

Read with care: the hand rule's higher power at small leads is bought with a false promotion
rate of 12% where 2.5% is intended, and at a lead of 0 most betting tests run to the cap
undecided, which is the cost E9-5 should weigh when it sets the cap and `d`.

**The interval shown beside a running test** is a 95% always-valid interval, so it too may be
read at any time: `mean_t +- sd_t * sqrt( 2 * (t * r2 + 1) / (t^2 * r2) * log( sqrt(t * r2 + 1) / 0.05 ) )`
with `r2 = 7.94 / 1500` (tightest near 1,500 boards), shown from board 300 (asymptotic
confidence sequence; Waudby-Smith, Arbour, Sinha, Kennedy and Ramdas,
https://arxiv.org/abs/2103.06476). It is for people to read. The decision is the two tests above,
which are exact; E9-5 reports how often this interval and the tests disagree.

**The panel check.** Promotion also requires that no panel cell shows the candidate worse than
the champion by more than the tolerance (`0.1` IMPs a board): for each panel member with at
least 300 boards against each of the two, the upper end of the 95% interval of
`cell(c, j) - cell(h, j)` must be above `-0.1`. This blocks a demonstrated regression. It does
not prove there is none: a small loss against one panel member can pass, and shows up later in
the rating table. Stating that limit is part of the rule.

**Several candidates at once.** Each test has its own `alpha`. With `k` candidates open the
chance that some equal-strength candidate is promoted is at most `k * alpha`; the rules version
may divide `alpha` by the number of open tests. A wrongly promoted candidate of equal strength
costs churn, not strength.

## 4. Where the next boards go

Within a purpose (rating precision, a pending test, an admission), the value of one more board
on pair `(i, j)` for a target contrast `u` (for a test, `u = e_c - e_h`; for a field score, the
field shares) is the drop in the target's variance:

```
gain(i, j) = (u' C a)^2 / (v_ij + a' C a),      a = e_i - e_j
```

and boards go to the pairs with the largest gain per CPU-second, subject to the caps in the
schedule (no pair's share more than doubling between epochs). A promotion test's own pair
always has the largest gain for that test; the formula matters for admissions and for the panel.

## 5. What E9-5 must show for these defaults to stand

1. Under a bootstrap of the real per-board values, with the candidate exactly equal to the
   champion, the promotion test promotes in at most 5% of runs at any horizon; the hand rule's
   rate is reported beside it.
2. Boards to a decision and power at true leads of 0.05, 0.1, 0.2 and 0.4, for the betting test,
   the hand rule and a single fixed-sample look.
3. The futility test stops a candidate that truly leads by 0.05 in at most 10% of runs.
4. Coverage of the rating table's 95% intervals with and without a pair effect of 0.3 on one
   pair, and with one pair's noise doubled.
5. Whether the gain rule of section 4 reaches a given field-score precision in fewer boards than
   equal shares.

## 6. Not specified here

- The field itself (which opponents, which shares): a decision for Max.
- Ratings of individual components (a net, a reader). The table rates players; a component is
  compared by entering two players that differ only in it.
- Any use of results from boards whose deal family a bundle trained on: they are training-only
  for that bundle (arena design, section 2).

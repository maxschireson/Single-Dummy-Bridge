# E9-2: boards needed to identify a system from finished boards (12 November 2026)

**Prediction evidence; registered protocol of `team/gen9:experiments/E9-2.md`.** Code:
`scripts/gen9_e9_2.py`, `bridge_harness/cards/match.py` on `feature/gen9-bidding-cards`. Data:
`result.json` (eps 0.05), `result-eps0.2.json` (eps 0.2). 1,000 boards a pair (999 for the rule
bidder: one deal skipped for a `rule_bidder.py` crash), all four seats bid by the true system, the
North-South pair's calls scored on its actual hands; 200 random orderings.

Likelihood of a call under a profile: a deterministic generator (the rule bidder, a compiled card's
bidder) gives `(1 - eps)` to its own call plus `eps` spread over the legal calls; a bidding net gives
`(1 - eps)` times its softmax plus `eps` uniform; `unknown` is the per-call average of the candidates'
distributions mixed 0.8 / 0.2 with uniform. Uniform prior over the candidates.

| Pair (truth first) | Boards where the two differ by > 0.5 nats | Boards to 0.95, median / 90th pct, eps 0.05 | eps 0.2 | Wrong card declared (prior 0.9 on it), eps 0.05 / 0.2 |
| --- | ---: | ---: | ---: | ---: |
| rule bidder precision vs standard | 26% | 3 / 8 | 3 / 8 | 3 / 8, 4 / 12 |
| house Gen 6 vs Gen 5 bidder | 14% | 20 / 37 | 48 / 72 | 36 / 55, 49 / 75 |
| 2/1 card, 1NT 15-17 vs 14-16 | 7.5% | 9 / 29 | 9 / 29 | 9 / 29, 18 / 47 |

Against the registered predictions: precision vs standard within about 10 boards (as predicted); the
house bidders in 20 to 50 (predicted about 50); the two no-trump ranges in 9 to 29, not hundreds.
The no-trump pair is fast because the profiles are deterministic and the truth is exactly one of
them: each board with a balanced 14 or 17 count in an opening seat is worth about 6 nats. A real
player who departs from a card, or a profile that is a learned net rather than the generator itself,
will be slower; the eps column is the first look at that (a looser reading roughly doubles the
house pair's count and the cost of a wrong declaration).

`unknown` when the true system is not a candidate: it took almost no weight in any pair once a few
hundred boards were in (the remaining candidate explains most calls better than a flattened mixture
of itself), and it is degenerate in the house pair at eps 0.2 (it equals the Gen 5 profile). A broad
model of "some other system" is still to be built; until then a pair whose system is not among the
profiles is read as its nearest profile.

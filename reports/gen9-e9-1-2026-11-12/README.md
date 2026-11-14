# E9-1 part 1: what the rule filter recovers on systems the scorer never saw (12 November 2026)

**Prediction evidence; the registered protocol of `team/gen9:experiments/E9-1.md`, part 1.** Code:
`scripts/gen9_e9_1.py` on `feature/gen9-bidding-cards`; data `result.json`. 2,000 random deals a
system (a few skipped for `rule_bidder.py` crashes or passed out), all four seats bid by the rule
bidder with the system's settings (the mixed table: house Gen 5 bidder against rule-bidder
precision, sides alternating). Deciders: the opening leader before the lead (three hidden hands) and
declarer at trick 1 (two hidden hands). Pool: 511 uniform random layouts consistent with the
decider's view, plus the true one. Gain `G = log(w(true) / sum w) - log(1/512)` in nats.

Readers: `S` hand-fit scorer v0; `S+F` plus the filter from the system's IR card
(`rb_cards.card_from_settings`, eps 0.05, negative inference); `S+F-ni` without negative inference;
`ceil` the card's filter alone at eps 0.001; `exact` the generator's own tables as a filter, eps 0.001,
which also covers the contexts the card leaves out (first 400 deals only: slow); `½S+F` a labelled
extra. In the mixed table the house side's seats are read by `S` under every reader.

| Generator | S | S+F | S+F-ni | ceil | exact (400 deals) | ½S+F | S+F recovers | ½S+F recovers |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 0.52 | 0.78 | 0.66 | 2.27 | 3.14 | 2.16 | 15% | 94% |
| precision | −5.79 | −4.62 | −4.83 | 2.18 | 3.18 | −0.32 | 15% | 69% |
| standard, 1NT 12-14 | −2.80 | −1.80 | −2.06 | 2.30 | 3.20 | 1.17 | 20% | 78% |
| standard, lighter openings | −0.94 | −0.65 | −0.80 | 2.22 | 3.19 | 1.48 | 9% | 77% |
| precision without relays, jumps, 2D | −5.98 | −4.86 | −5.09 | 2.08 | 3.05 | −0.48 | 14% | 68% |
| mixed: house Gen 5 vs precision | −0.02 | 0.37 | 0.30 | 2.95 | 2.69 | 2.05 | 13% | 70% |

About 4,000 decisions each; standard errors 0.02 to 0.22 (largest for `S` on precision). "Recovers"
is the share of the gap between `S` and `ceil`. Slices in `result.json`: leader and declarer,
contested and uncontested.

What it says:
- The hypothesis's first part fails: multiplying the filter onto the scorer at full weight recovers
  9 to 20% of the gap, not half. The scorer misreads these systems so badly (down to −6 nats, far
  below knowing nothing) that the card's evidence cannot outvote it.
- Halving the scorer's weight recovers 68 to 94%. The scorer's misreadings are confident; the
  weight on it should be a per-profile quantity learned from finished boards (a grid like the play
  factor), and 0 for a profile the scorer was not trained on. This supports the `card` profile in
  the mixture.
- Negative inference from the tables' order is worth 0.07 to 0.26 nats over the call's own meaning.
- `exact` beats the card's ceiling by about 0.9 nats: the IR cards for these settings cover about 30%
  of calls (openings, overcalls, no-trump relays); the rest of the meaning is in contexts the cards
  leave out. Wider coverage is worth about as much again.
- The leader gains far more than declarer (more hidden hands, and the opening bidder's partner's
  calls are covered).

## Supplement: the scorer's weight (`weight-grid.json`)

Same protocol, 500 deals a system (about 1,000 decisions), readers `w * S + F` for a grid of `w`:

| Generator | w = 0 | 0.1 | 0.25 | 0.5 | 0.75 | 1 | S alone |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| standard | 2.29 | **2.74** | 2.73 | 2.25 | 1.62 | 0.92 | 0.66 |
| precision | 2.19 | **2.35** | 1.66 | −0.08 | −2.05 | −4.13 | −5.34 |
| standard, 1NT 12-14 | 2.27 | **2.61** | 2.34 | 1.14 | −0.34 | −1.91 | −2.97 |
| mixed: house Gen 5 vs precision | 2.98 | **3.08** | 2.82 | 2.09 | 1.27 | 0.39 | 0.01 |

On every generator the best weight is about 0.1: the scorer still adds 0.1 to 0.45 nats at that weight
over the card alone, and costs more and more above it.

## Supplement, 12 Nov 09:21 UTC: when the player matches a profile, does the card post-filter help?

Max's question in the Gen 9 brief: "Even when they match a profile their card post-filters the net?"
Same protocol as part 1 (opening leader before the lead and declarer at trick 1, pool 512, gain of the
true layout in nats), on auctions bid at all four seats by a house net, read with a card the net's
profile is near. 400 deals a row (seeds 9931, 10931, 11931; readers paired within a row);
`house-postfilter.json`, `scripts/gen9_e9_1.py --systems house-gen5:<card>,...`.

| Auctions / card | S | F alone | S+F | R (replay) | R+F |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gen 5 / house-gen5-fit (the best card for Gen 5) | 3.72 ± 0.08 | 1.98 ± 0.09 | 3.30 ± 0.09 | 4.08 ± 0.08 | 3.73 ± 0.09 |
| Gen 5 / two-over-one | 3.64 ± 0.08 | 1.75 ± 0.10 | 3.05 ± 0.10 | 3.95 ± 0.08 | 3.52 ± 0.10 |
| Gen 6 / house-gen5-fit | 3.64 ± 0.08 | 1.89 ± 0.09 | 3.06 ± 0.10 | 4.07 ± 0.08 | 3.61 ± 0.10 |

- No. Multiplying the card's filter (eps 0.05) onto a matching profile's reading costs 0.35-0.6 nats,
  whether the profile is read by the scorer (S → S+F) or by replay (R → R+F), even with the card fitted
  to that very bidder. The card is broken on about 15% of the calls it covers (profile-distance report),
  and each break costs a true layout log 0.05.
- Without negative inference the cost is smaller (S+F-ni 3.47, 3.25, 3.24) but still a cost.
- The card alone reads about half of what the profile's own reader does (1.8-2.0 against 3.6-4.1).
- So for a player mapped to a held profile, the card's job is the mapping (the arrival prior, and the
  `card` profile in the mixture that takes over if the player stops bidding like the profile), not a
  filter on the profile's reading. This is what the shell does now.

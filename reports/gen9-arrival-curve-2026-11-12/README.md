# How fast the shell's profile probabilities move for a guest (12 November 2026)

**Prediction evidence** for G9-D6 (no play). `scripts/gen9_arrival_curve.py`: a guest partnership bids
with house Gen 5, its opponents with Gen 6, alternating sides, 100 boards (seed 9141). The guest declares
`rb-standard` (guest-b). The prior is `player_model.arrive` from the card's distances to the three held
systems (300 deals): card 0.70, flat 0.18, house-gen5 0.042, house-dds40k 0.041, house-gen6 0.039. After
k boards the statistic is the sum of `cards.match.profile_evidence` over k boards (20 random orders), and
the probabilities are `player_model.believed` (temper 1, floor 0.02).

Believed probability after k boards, with the held systems' call models at the old defaults (eps 0.05,
temperature 1) and at the new ones (eps 0.02, temperature 0.25):

| k | gen5 + dds40k, T 1 | gen5 + dds40k, T 0.25 | gen6, T 1 | gen6, T 0.25 | card, T 1 | card, T 0.25 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0 | 0.08 | 0.08 | 0.04 | 0.04 | 0.70 | 0.70 |
| 2 | 0.17 | 0.23 | 0.08 | 0.08 | 0.56 | 0.52 |
| 5 | 0.34 | 0.53 | 0.18 | 0.14 | 0.32 | 0.24 |
| 10 | 0.59 | 0.88 | 0.17 | 0.05 | 0.18 | 0.06 |
| 20 | 0.86 | 0.99 | 0.12 | 0.006 | 0.016 | 0.004 |
| 50 | 0.98 | 0.99 | 0.013 | 0.004 | 0.004 | 0.004 |

Mean log-likelihood a board of the guest's calls: T 1: gen5 −0.673, dds40k −0.674, gen6 −0.813, flat
−0.98, card −1.71; T 0.25: gen5 −0.205, dds40k −0.208, gen6 −0.967, flat −0.73, card −1.48.

- **house-gen5 and house-dds40k cannot be told apart** (0.003 nats a board). Gen 5 is the 40,000-deal DDS
  bidder after a small fine-tune (models/bidding/gen5-2026-11-10/README.md); for reading they are one system,
  and the pair together is the guest's profile. After 100 boards they split about 0.58 / 0.41.
- **The temperature matters for identifying a greedy bidder.** The house nets bid their argmax; at
  temperature 1 Gen 6 explains Gen 5's calls nearly as well as Gen 5 does (0.09 nats a board on 60 other
  boards, seed 9143, eps 0.02; 0.14 here). Sharpening to 0.25 makes the gap 0.46 (0.10: 0.69) and the true
  model's own calls more likely (−0.49 to −0.20 a board). `held_systems` now defaults to eps 0.02,
  temperature 0.25. A guest who does not bid greedily is punished harder at a low temperature; the floor
  bounds a call's cost at about log(0.02 / legal calls).
- **The declared card does worse than `flat`** on this guest (−1.48 against −0.73): rb-standard is broken
  on about 14% of the calls it covers and each break costs about log 0.05 under the card's prior eps.
- With the new defaults guest-b is mapped to its profile within an epoch's first 10-20 boards; the wrong
  near profile (gen6) is below 0.01 by 20 boards.

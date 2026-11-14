# What a bidding style costs (14 November 2026)

Max, 19:31 UTC: two bidding style dimensions (aggressive vs conservative; points vs shape), "then put some randomization
in", with the same disclosure and correlation rules as the card-play styles. Code: `bridge_harness/bid_style.py`,
`bridge_harness/persona.py`, `scripts/bid_style_cost.py`; description in `docs/styles.md`.

## Method

- Random deals (seed 101 for the 12,000-deal runs, seed 1 for the 3,000-deal runs), dealer and vulnerability drawn.
- The Gen 6 bidder SiD (rollout) Stu R4c bids with (`artifacts/gen6/bidder.keras` in the `stu4c-put` bundle).
- Each deal bid twice: plain at all four seats, and with North-South styled (East-West plain). The styled seats'
  random numbers come from one stream, seeded the same for every style.
- Scored double dummy: DDS tricks for the final contract, NS score difference in IMPs (styled minus plain), averaged
  over all deals; `±` is one standard error over deals.
- Not measured: card play, opponents or partners who read the style (no reader is built), and anything single-dummy.
  The cost is the style's own bidding loss against its own plain bidding, with opponents who bid as before.

Columns: boards changed = share of deals whose NS result differs; calls changed = share of styled decisions that
differ from the plain call; final level = mean level of the final contract; lean corr = correlation, over styled
decisions, between (styled action minus plain action) and the hand's shape lean (z of distribution points minus z of
high-card points). A shape bidder should be positive, a points bidder negative.

## Results with the rule as merged (exchange-rate weight, random share drawn by the bidder's probabilities)

12,000 deals. Personas: `persona.draw` (bidding weights uniform on [-scale, scale] per dimension, random share uniform
on [0.05, 0.20], `near` fixed or drawn per persona), one persona per deal, 600 personas cycled.

| near | style | IMPs/board | boards changed | calls changed | final level (plain → styled) | lean corr |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | random only 0.15 | -0.013 ± 0.011 | 2.8% | 0.7% | 3.27 → 3.27 | +0.001 |
| 6 | aggressive +2, random 0.15 | -0.173 ± 0.032 | 20.7% | 5.9% | 3.27 → 3.45 | +0.032 |
| 6 | aggressive -2, random 0.15 | -0.209 ± 0.029 | 18.3% | 5.2% | 3.27 → 3.13 | -0.033 |
| 6 | shape +2, random 0.15 | -0.118 ± 0.029 | 16.9% | 4.8% | 3.27 → 3.34 | +0.130 |
| 6 | shape -2, random 0.15 | -0.131 ± 0.028 | 15.0% | 4.3% | 3.27 → 3.33 | -0.122 |
| 6 | population of 600, weights ±2 (mean abs 1.02) | -0.095 ± 0.026 | 13.9% | 3.8% | 3.27 → 3.31 | +0.003 |
| 6 | population of 600, weights ±3 (mean abs 1.54) | -0.237 ± 0.031 | 18.7% | 5.3% | 3.27 → 3.33 | +0.003 |
| 6 | population of 600, weights ±4 (mean abs 2.05) | -0.314 ± 0.034 | 22.7% | 6.7% | 3.27 → 3.35 | +0.004 |
| 3–6 per persona | population of 600, weights ±2 (mean abs 0.99) | -0.100 ± 0.025 | 13.1% | 3.6% | 3.27 → 3.30 | +0.011 |
| 3–6 per persona | population of 600, weights ±3 (mean abs 1.48) | -0.175 ± 0.029 | 17.8% | 5.1% | 3.27 → 3.32 | +0.012 |
| 3–6 per persona | population of 600, weights ±4 (mean abs 1.98) | -0.233 ± 0.032 | 21.1% | 6.2% | 3.27 → 3.34 | +0.010 |

- The random share now costs little (0.013 ± 0.011 at 15%; 0.7% of calls change): draws follow the bidder's own
  probabilities, so calls it rates low are rarely drawn.
- Aggressive and conservative move the final contract the way they say (3.27 → 3.45 at +2, → 3.13 at −2) and cost
  about the same; shape and points cost less and move which hands bid (lean corr +0.13 and −0.12), not much the
  average level. Both shape directions raise the mean level slightly (3.33–3.34) although the lean is zero on average;
  probably because more action is more often available than less (when the bidder's best call is already a pass, a hand
  leaning towards less has nothing lower to take). Not checked.
- **Chosen dose: `near` 6, weights uniform on ±3: 0.237 ± 0.031 IMP a board across the population** (the persona
  defaults now). Individual personas range from about 0 (both weights near 0) to roughly the single-style rows at |2| and
  beyond; nothing here measures the spread per persona directly.
- Card-play styles add little on top in self-play: since 05:40 UTC they choose only among cards tied exactly double
  dummy.

The target is our reading of Max's 03:35–03:50 UTC messages: styles costing "half an imp or so" well represented, "some
who give up an imp even", but a population average of half an IMP "was too much".

## The two earlier versions

**Uniform random share** (same exchange-rate weight; 12,000 deals). A 15% uniform share alone cost 0.17 IMP a board at
`near` 6, most of a persona's budget spent on noise; replaced by the bidder-weighted draw above.

| near | style | IMPs/board | boards changed | calls changed | final level (plain → styled) | lean corr |
| --- | --- | --- | --- | --- | --- | --- |
| 6 | random only 0.15 | -0.171 ± 0.023 | 11.1% | 3.0% | 3.27 → 3.30 | +0.010 |
| 6 | aggressive +2, random 0.15 | -0.350 ± 0.036 | 26.5% | 8.0% | 3.27 → 3.48 | +0.030 |
| 6 | aggressive -2, random 0.15 | -0.333 ± 0.033 | 24.7% | 7.6% | 3.27 → 3.15 | -0.028 |
| 6 | population of 600, weights ±1 (mean abs 0.51) | -0.157 ± 0.027 | 14.6% | 4.1% | 3.27 → 3.31 | +0.007 |
| 6 | population of 600, weights ±2 (mean abs 1.02) | -0.202 ± 0.031 | 19.7% | 5.7% | 3.27 → 3.33 | +0.009 |
| 6 | population of 600, weights ±3 (mean abs 1.54) | -0.350 ± 0.035 | 24.0% | 7.3% | 3.27 → 3.35 | +0.009 |
| 3–6 per persona | population of 600, weights ±1 (mean abs 0.49) | -0.120 ± 0.024 | 12.0% | 3.4% | 3.27 → 3.30 | +0.008 |
| 3–6 per persona | population of 600, weights ±2 (mean abs 0.99) | -0.166 ± 0.029 | 17.1% | 4.9% | 3.27 → 3.32 | +0.009 |
| 3–6 per persona | population of 600, weights ±3 (mean abs 1.48) | -0.237 ± 0.031 | 21.1% | 6.3% | 3.27 → 3.33 | +0.011 |

3,000 deals, the same rule, narrower caps:

| near | style | IMPs/board | boards changed | calls changed | final level (plain → styled) | lean corr |
| --- | --- | --- | --- | --- | --- | --- |
| 2 | aggressive +0.5, random 0.15 | -0.075 ± 0.036 | 7.1% | 1.9% | 3.31 → 3.35 | +0.006 |
| 2 | aggressive -0.5, random 0.15 | -0.059 ± 0.040 | 8.3% | 2.2% | 3.31 → 3.26 | -0.011 |
| 2 | aggressive +1, random 0.15 | +0.072 ± 0.048 | 12.2% | 3.3% | 3.31 → 3.39 | +0.021 |
| 2 | aggressive -1, random 0.15 | -0.084 ± 0.047 | 12.3% | 3.3% | 3.31 → 3.23 | -0.021 |
| 2 | aggressive +2, random 0.15 | -0.038 ± 0.060 | 18.0% | 5.3% | 3.31 → 3.44 | +0.017 |
| 2 | aggressive -2, random 0.15 | -0.173 ± 0.056 | 18.0% | 5.2% | 3.31 → 3.18 | -0.014 |
| 2 | shape +1, random 0.15 | +0.041 ± 0.046 | 9.8% | 2.8% | 3.31 → 3.32 | +0.095 |
| 2 | shape -1, random 0.15 | -0.097 ± 0.043 | 9.7% | 2.5% | 3.31 → 3.32 | -0.074 |
| 2 | shape +2, random 0.15 | -0.066 ± 0.053 | 14.2% | 4.0% | 3.31 → 3.33 | +0.109 |
| 2 | shape -2, random 0.15 | -0.111 ± 0.050 | 13.0% | 3.6% | 3.31 → 3.34 | -0.082 |
| 2 | random only 0.15 | -0.020 ± 0.026 | 3.4% | 0.8% | 3.31 → 3.30 | +0.011 |
| 2 | population of 300, weights ±1 (mean abs 0.49) | -0.039 ± 0.038 | 8.0% | 2.2% | 3.31 → 3.31 | -0.012 |
| 3 | aggressive +0.5, random 0.15 | -0.096 ± 0.040 | 9.0% | 2.4% | 3.31 → 3.35 | +0.014 |
| 3 | aggressive -0.5, random 0.15 | -0.081 ± 0.043 | 9.3% | 2.6% | 3.31 → 3.27 | -0.008 |
| 3 | aggressive +1, random 0.15 | -0.022 ± 0.051 | 13.3% | 3.7% | 3.31 → 3.40 | +0.020 |
| 3 | aggressive -1, random 0.15 | -0.125 ± 0.051 | 13.6% | 3.8% | 3.31 → 3.23 | -0.018 |
| 3 | aggressive +2, random 0.15 | -0.062 ± 0.063 | 20.5% | 6.0% | 3.31 → 3.46 | +0.024 |
| 3 | aggressive -2, random 0.15 | -0.206 ± 0.059 | 19.6% | 5.7% | 3.31 → 3.17 | -0.025 |
| 3 | shape +1, random 0.15 | -0.003 ± 0.050 | 11.8% | 3.4% | 3.31 → 3.32 | +0.089 |
| 3 | shape -1, random 0.15 | -0.120 ± 0.046 | 11.4% | 3.1% | 3.31 → 3.33 | -0.088 |
| 3 | shape +2, random 0.15 | -0.088 ± 0.060 | 17.4% | 5.2% | 3.31 → 3.35 | +0.117 |
| 3 | shape -2, random 0.15 | -0.109 ± 0.056 | 15.8% | 4.5% | 3.31 → 3.34 | -0.093 |
| 3 | random only 0.15 | -0.039 ± 0.032 | 5.3% | 1.4% | 3.31 → 3.31 | +0.019 |
| 3 | population of 300, weights ±1 (mean abs 0.49) | -0.076 ± 0.045 | 9.9% | 2.6% | 3.31 → 3.33 | -0.012 |
| 6 | aggressive +0.5, random 0.15 | -0.249 ± 0.054 | 14.7% | 4.2% | 3.31 → 3.38 | +0.019 |
| 6 | aggressive -0.5, random 0.15 | -0.169 ± 0.052 | 14.7% | 4.1% | 3.31 → 3.28 | -0.011 |
| 6 | aggressive +1, random 0.15 | -0.102 ± 0.059 | 17.6% | 5.3% | 3.31 → 3.42 | +0.015 |
| 6 | aggressive -1, random 0.15 | -0.149 ± 0.056 | 17.8% | 5.2% | 3.31 → 3.24 | -0.022 |
| 6 | aggressive +2, random 0.15 | -0.224 ± 0.072 | 25.7% | 7.9% | 3.31 → 3.51 | +0.037 |
| 6 | aggressive -2, random 0.15 | -0.309 ± 0.067 | 24.3% | 7.4% | 3.31 → 3.17 | -0.030 |
| 6 | shape +1, random 0.15 | -0.068 ± 0.060 | 17.1% | 5.0% | 3.31 → 3.36 | +0.089 |
| 6 | shape -1, random 0.15 | -0.215 ± 0.054 | 16.0% | 4.6% | 3.31 → 3.35 | -0.057 |
| 6 | shape +2, random 0.15 | -0.315 ± 0.071 | 23.7% | 7.3% | 3.31 → 3.40 | +0.127 |
| 6 | shape -2, random 0.15 | -0.322 ± 0.066 | 21.1% | 6.5% | 3.31 → 3.39 | -0.095 |
| 6 | random only 0.15 | -0.187 ± 0.044 | 10.2% | 2.8% | 3.31 → 3.33 | +0.007 |
| 6 | population of 300, weights ±1 (mean abs 0.49) | -0.061 ± 0.050 | 13.8% | 4.0% | 3.31 → 3.34 | -0.006 |

**Most or least action whatever the weight** (the first version; 3,000 deals). Only the weight's sign and `near` mattered:
any nonzero weight cost about the same at a given `near`, and the population (weights ±1) cost as much as a full-weight
style. It also made partial knowledge meaningless (a reader told 30% of a style modelled all of it). Population rows:
`near` 2: −0.082 ± 0.059; 3: −0.321 ± 0.071; 4: −0.505 ± 0.081; 5: −0.818 ± 0.090.

| near | style (random 0.15) | IMPs/board |
| --- | --- | --- |
| 0.5 | aggressive +1 | -0.005 ± 0.030 |
| 0.5 | aggressive -1 | -0.039 ± 0.034 |
| 0.5 | shape +1 | -0.001 ± 0.034 |
| 0.5 | shape -1 | -0.055 ± 0.032 |
| 0.5 | aggressive +0.7, shape +0.7 | -0.034 ± 0.032 |
| 0.5 | random only | -0.011 ± 0.014 |
| 1 | aggressive +1 | -0.001 ± 0.043 |
| 1 | aggressive -1 | -0.084 ± 0.044 |
| 1 | shape +1 | +0.021 ± 0.046 |
| 1 | shape -1 | +0.001 ± 0.041 |
| 1 | aggressive +0.7, shape +0.7 | -0.001 ± 0.041 |
| 1 | random only | -0.017 ± 0.021 |
| 1.5 | aggressive +1 | -0.000 ± 0.052 |
| 1.5 | aggressive -1 | -0.097 ± 0.051 |
| 1.5 | shape +1 | +0.007 ± 0.052 |
| 1.5 | shape -1 | -0.034 ± 0.049 |
| 1.5 | aggressive +0.7, shape +0.7 | -0.036 ± 0.052 |
| 1.5 | random only | +0.010 ± 0.018 |
| 2 | aggressive +1 | -0.080 ± 0.061 |
| 2 | aggressive -1 | -0.174 ± 0.058 |
| 2 | shape +1 | -0.073 ± 0.060 |
| 2 | shape -1 | -0.081 ± 0.056 |
| 2 | aggressive +0.7, shape +0.7 | -0.091 ± 0.061 |
| 2 | random only | -0.020 ± 0.026 |
| 3 | aggressive +1 | -0.317 ± 0.075 |
| 3 | aggressive -1 | -0.349 ± 0.069 |
| 3 | shape +1 | -0.231 ± 0.072 |
| 3 | shape -1 | -0.299 ± 0.069 |
| 3 | aggressive +0.7, shape +0.7 | -0.340 ± 0.077 |
| 3 | random only | -0.039 ± 0.032 |

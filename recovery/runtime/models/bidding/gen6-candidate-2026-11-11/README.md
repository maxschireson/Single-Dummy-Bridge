# Gen 6 candidate bidder: graded alternatives — designated 11 November 2026

Max named the graded-alternatives bidder the Gen 6 candidate bidder. It is a candidate, not a
promotion. Every strength figure below is double-dummy scored and card play is untested. This
folder changes no config, registry or arena bot.

Run `python models/bidding/gen6-candidate-2026-11-11/restore_model.py` from the repository root
to rebuild the BEN-compatible `bidder.keras` (SHA-256
`5b7ea2558581df39d6517f86f459000ed1ef3a2fb1e8120563c70b343b95e7ff`). The script checks every
chunk and the complete file. The file is byte-identical to `graded_lr3e5_2pass.keras` in
`training/graded-alternatives-20261110/`, which holds the training code, logs and full results.
It loads with `bridge_harness.bidding_ppo.Policy.load`; no inference code change is needed.

## What it is

- The same network as the Gen 5 bidder: three 256-unit LSTM layers, 193 BEN features in,
  40 calls out. The BatchNormalization statistics are identical to Gen 5's; the other weight
  tensors differ from Gen 5's by 0.7% to 2.1% (relative L2).
- Trained from the BEN base (`GIB-BBO-8742_2026-10-23-E30.keras`, `b0dff3df…`) by grading every
  plausible alternative call on 35,000 of the 40,000 solved training deals: two passes at
  learning rate 3e-5 with a 0.02 KL anchor to the base.
- It does not see spot cards. Its hand input is A/K/Q/J/T plus a count of lower cards per suit,
  as in BEN; re-dealing the 2–9s within each suit changed none of 8,192 auctions. It is not the
  spot-card bidder that `configs/gen6-bidding-systems.json` on
  `research/gen6-system-aware-policy-20261111` lists as awaited.

## Strength

Greedy duplicate, both rooms, double-dummy, IMPs per board ± one standard error, on deals not
used in training (from `training/graded-alternatives-20261110/README.md`):

| Opponent | Review deals (5,000) | New deals (2,270) | Pooled (7,270) |
| --- | ---: | ---: | ---: |
| Gen 5 bidder (`play50_anchor002`, `9ee52f3b…`) | +0.213 ± 0.046 | +0.331 ± 0.068 | +0.250 ± 0.038 |
| PPO-40k | +0.217 ± 0.046 | +0.327 ± 0.069 | +0.251 ± 0.038 |
| BEN base | +0.293 ± 0.049 | +0.398 ± 0.075 | +0.326 ± 0.041 |

Against Gen 5 it won 507, lost 367 and tied 4,126 of the review deals, and won 223, lost 141 and
tied 1,906 of the new deals.

`verify_candidate.py` repeats the new-deals comparison with Gen 5 using the harness's own code
(`Policy.load` and `paired_auctions`). Run on 11 November with TensorFlow 2.21.0 it gave
+0.3313 ± 0.0681, with 223 won, 141 lost and 1,906 tied.

```bash
python models/bidding/gen6-candidate-2026-11-11/verify_candidate.py \
  --gen5 PATH/TO/gen5/bidder.keras --harness PATH/TO/A/GEN5-OR-GEN6/CHECKOUT
```

`--harness` is needed because this branch sits on `main`, which has no
`bridge_harness/bidding_env.py`.

## How far it is from Gen 5

Fresh random deals, each bid once by Gen 5 and once by the candidate:

- With all four seats on one bidder, the auction differs on 26.7% of deals and the contract or
  declarer on 20.5% (16,384 deals).
- Run along Gen 5's auctions, the candidate would choose a different call at 3.0% of calls
  (8,192 deals).
- With only East–West on the candidate, the auction differs from the all-Gen 5 auction on 14.9%
  of deals (8,192 deals).

## Effect on the auction belief net trained on Gen 5 auctions

The joint net of `research/joint-auction-belief-20261110`, used unchanged on candidate auctions:

- Likelihood of the true layout, nats over uniform: 6.18 ± 0.02 on Gen 5 auctions and
  6.10 ± 0.02 on candidate auctions (16,384 deals). Where the auction changed: 5.75 ± 0.04,
  against 6.02 ± 0.03 on the Gen 5 auction of the same deals.
- Share of its sampled layouts that pass the bidder's test: 33.7% on Gen 5 auctions, 31.3% on
  candidate auctions (300 deals; paired change −2.4 ± 0.8 points).
- Opening lead, 54 recorded arena deals, 32 layouts per arm, tricks per lead scored on held-out
  exact-posterior layouts: exact layouts minus the net +0.002 ± 0.010 on candidate auctions and
  +0.015 ± 0.008 on Gen 5 auctions; the net minus the v5 belief sampler +0.026 ± 0.011 and
  +0.024 ± 0.011.
- With the leader's side on Gen 5 and the declaring side on the candidate: 6.10 ± 0.02 nats
  (8,192 deals, both seatings), and 33.1% ± 1.6 of layouts passing against 34.4% ± 1.6 at an
  all-Gen 5 table (200 leads each).

The figures in this section and the previous one were measured in a Claude session on
10–11 November. Their scripts and records are not in the repository. The lead test resolves
about 0.02 tricks, so a smaller loss would not show.

## Not tested

- Card play. Every strength figure is double-dummy. In the training report, 52% of the contracts
  it reaches that the base does not make double-dummy.
- Any arena match with this bidder.
- Opponents that adapt; more than two passes; fresh deals for each pass.

## Licence

Fine-tuned BEN weights: `BEN-LICENSE.txt` applies. See also `CREDITS.md`.

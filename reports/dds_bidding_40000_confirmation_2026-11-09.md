# Exact 40,000-pair bidding candidate: fresh 5,000-pair review

The frozen candidate scored **+0.0626 IMP/board**, with a descriptive 95%
interval **[+0.00681, +0.11839]**, on 5,000 fresh greedy paired auctions.
This is a positive result after 40,000 training pairs (80,000 training auctions,
314 PPO updates). No real card play was used. Production remains parked at the
requested checkpoint; no promotion or threshold change has been applied.

| Metric | Result |
|---|---:|
| Total IMPs | +313 |
| Standard error, IMP/board | 0.028459 |
| Wins / losses / ties | 172 / 156 / 4,672 |
| Unique held-out deals | 5,000 |
| Overlap with previous 21,904-candidate confirmation | 0 |
| Active review time | 1,402.76 seconds |

The user requested this earlier 40k checkpoint instead of 50k, with a direct
5k confirmation and no intervening development screen. All 5k pairs were
completed. The model, split, seed and evaluation policy stayed frozen throughout.
The interval is descriptive; it is not the earlier campaign's multiplicity-
adjusted promotion gate. The additional look must not be represented as a
preregistered independent promotion decision.

The 21,904 candidate previously scored +0.0744 on a different 5k sample. These
point estimates do not establish that 40k is weaker: the samples differ and the
intervals overlap. Both suggest a modest positive change relative to original
BEN net-only bidding, which is also the current parent and old league.

Snapshot SHA256:
`51cd49e12a28995006ae12a7fae5b4088410d59a6523b70cdfcac62f6b8e98b4`.
Fresh test seed: `2326250810`. Original runtime source unchanged. The separate
40k model/Adam/DDS milestone remains preserved; source commits contain no
weights, datasets or logs.

[Download the complete 5,000-pair results](https://chatgpt.com/library?file_id=libfile_fde3_f-59e9e5bcacd08191b36a104a196585ad_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).

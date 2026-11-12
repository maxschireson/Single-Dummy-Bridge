# Initial Gen5 bidder — 10 November 2026

Max selected candidate 2 (`play50_anchor002`) as the initial Gen5 bidder.
This is a provisional operational choice, not a statistically established gain.

Run `python models/bidding/gen5-2026-11-10/restore_model.py` from the repository
root to reconstruct the native BEN-compatible `bidder.keras`. The script checks
every chunk and the complete model's SHA-256. No inference code change is needed.

The bidder starts from the validated 40,000-deal DDS bidder. It received 2,048
additional duplicate training pairs, sampled 50% from clean actual-play deals
and 50% from existing DDS-scored training deals. Original BEN KL weight is 0.02,
learning rate 2.5e-6, minibatch 64, and two PPO epochs per batch. This is KL
retention on visited observations, not replay of the unavailable BEN base corpus.
The six-way experiment shares architecture, initial weights and training budget.

All retained historical cardplay excludes v4/v4p on both sides, including aliases
of the bad policy hash. Historical rewards require exact auction matching.
Missing auctions use frozen clean Gen3 cardplay with 32 samples. Replays are
cached by full auction, deal, dealer, vulnerability and model/solver identity.

| Evaluation against unchanged 40k bidder | Families | Mean IMP/board | SE | Approx. 95% interval |
| --- | ---: | ---: | ---: | --- |
| Clean-play development | 199 | +0.0151 | 0.0128 | −0.0100 to +0.0402 |
| Existing DDS development | 1,000 | +0.0160 | 0.0294 | −0.0416 to +0.0736 |
| Untouched clean-play final test | 192 | +0.0625 | 0.0625 | −0.0600 to +0.1850 |

Selection was frozen before the final test was opened. The final test is one
12-IMP win and 191 ties: a sparse, roughly one-standard-error result, not evidence
of a reliable strength improvement. The prior DDS development set was used in
earlier work and is not an untouched test. Uncertainty is across deal families;
it does not capture all variation from stochastic cardplay or heterogeneous
historical clean bot versions.

The other four candidates continue training and all six will be compared on
development. The original final test is now reserved for candidate 2 only.
A later selected replacement requires fresh confirmation data. No other model
will automatically replace this initial Gen5 bidder. Existing arena run manifests
remain immutable; new runs can point to this restored model.

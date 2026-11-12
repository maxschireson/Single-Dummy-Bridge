# Promoted v5 policy component

Max authorized promotion of the attention policy on 2026-11-10. This is the
policy component for assembling v5; no bidding/belief choice or arena restart
is implied. Restore with `python models/cardplay/gen5-2026-11-10/restore_policy.py`.
Use the restored `policy.npz` with the existing auction-policy player and the
updated `AuctionSelectorWeights` loader. NumPy inference needs no TensorFlow.

99,161 parameters; selected epoch 4 of 8. Initialized from later v3; trained
on 410,694 outcome rows from the clean incremental corpus of 5,679 families.
All active v4/v4p play excluded. Predicts remaining partnership tricks; no IMP
loss. Family splits and equal family weights are preserved. V2-era experience
is inherited through the parent checkpoint, not replayed as new data.

Held-out outcome MSE: 0.572980 versus v3 0.609247 (5.95% lower).
External unused clean audit corpus: 21,413 comparisons / 1,638 families;
+0.016782 IMP per comparison versus v3, SE 0.007775, 2.16 sigma,
95% CI [0.001531, 0.032033]. Includes recursive branches; family-clustered
uncertainty. This is not a full-game strength estimate; interval unadjusted for
multiple candidates. Original held-out mainline gain +0.006722, inconclusive.

Scorer-only CPU timing approximately 0.25 ms per position. Full comparison,
training histories, source provenance and checksums are included here.

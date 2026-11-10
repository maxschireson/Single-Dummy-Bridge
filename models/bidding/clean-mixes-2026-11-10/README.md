# Six-way clean bidding refresh: completed 2026-11-10

All six frozen candidates completed 2,048 duplicate training pairs each. Candidate 2 (play50_anchor002) remains the user-selected initial Gen5 bidder, published in ../gen5-2026-11-10. The other five are research candidates only. No later development result changes that selection.

## Development results

All numbers are candidate minus validated40k parent. SEs and 95% normal intervals use family-level score differences. Clean-play development has 199 families; the DDS comparison uses the previous 1,000-family development set, not a new test set. Both rooms are grouped within a family.

| Candidate | Actual-play / DDS mix | BEN KL weight | Clean-play IMP/board ± SE | Clean-play 95% CI | DDS IMP/board ± SE | DDS 95% CI |
|---|---|---|---|---|---|---|
| 1: play25_anchor002 | 25% / 75% | 0.02 | -0.0691 ± 0.0577 | [-0.1823, +0.0441] | +0.0290 ± 0.0262 | [-0.0224, +0.0804] |
| 2: play50_anchor002 | 50% / 50% | 0.02 | +0.0151 ± 0.0128 | [-0.0100, +0.0402] | +0.0160 ± 0.0294 | [-0.0416, +0.0736] |
| 3: play75_anchor002 | 75% / 25% | 0.02 | +0.0151 ± 0.0128 | [-0.0100, +0.0402] | -0.0040 ± 0.0296 | [-0.0621, +0.0541] |
| 4: play25_anchor020 | 25% / 75% | 0.20 | -0.0603 ± 0.0603 | [-0.1785, +0.0579] | +0.0210 ± 0.0228 | [-0.0237, +0.0657] |
| 5: play50_anchor020 | 50% / 50% | 0.20 | +0.0126 ± 0.0131 | [-0.0130, +0.0382] | +0.0020 ± 0.0262 | [-0.0494, +0.0534] |
| 6: play75_anchor020 | 75% / 25% | 0.20 | +0.0151 ± 0.0128 | [-0.0100, +0.0402] | -0.0060 ± 0.0273 | [-0.0595, +0.0475] |

Every development interval includes zero. Candidates 2, 3, and 6 tie on the clean-play mean. These sparse differences provide no convincing evidence of a superior mix or KL weight. Comparing six variants also entails selection effects; the displayed intervals are individual, not multiplicity-adjusted. Training loss is not evidence of better bidding.

## Frozen final test and selection

Max selected candidate 2 before opening the 192-family final set. Its final result is +12 total IMP, +0.0625 IMP/board, SE 0.0625, approximate 95% CI [-0.0600, +0.1850]: one win and 191 ties. This is inconclusive. Only candidate 2 and its parent comparator were evaluated on that set. The immutable selection.json field test_unopened records the state at selection time; it is deliberately preserved. A replacement requires fresh confirmation data and user authorization.

## Data, rewards, and training

The filtered historical corpus contains 3,824 games from 1,868 families, split 1,477 train / 199 development / 192 final. All v4/v4p cardplay was excluded on both sides, including aliases of the bad policy SHA e179a71ed132dcd0f9ca06b486ec087e9f5b26edb4210e99ed2e04c9439b21ed. Historical v2/v3/v4b outcomes are treated as compatible only for identical auctions with the matching deal orientation, dealer and vulnerability. Missing exact auctions are replayed using frozen clean Gen3 at 32 samples. Cache identity includes the complete auction, deal, dealer, vulnerability, model and solver identity. Same-strain reward substitution is superseded and is not used in this run.

The six mixes cross 25/50/75% actual-play training with KL weights 0.02/0.20. Every model starts at the validated 40k DDS bidder and uses the original BEN anchor, learning rate 2.5e-6, 2,048 pairs, 128-pair collection batches, minibatch 64 and two PPO epochs per batch. KL is measured on collected observations; it does not replay the original BEN training corpus, which is unavailable. Changing the play/DDS mix is an explicit distribution experiment, not proof that training matches a deployment population. The small development comparison cannot resolve distribution shift or identify a reliably better mix.

Frozen input and source hashes, replay-model/solver identities and software version are recorded in manifest.json. Per-candidate training summaries accompany the models. Raw development outcomes and the already completed candidate-2 final outcomes are compressed losslessly.

## Technical recovery changes

Collection, cardplay and gradient updates run in separate processes after combined TensorFlow/DDS processes were killed. Pending observations and RNG state are persisted between stages; model and Adam state are checkpointed per completed batch. The update stage loads pending arrays once, fixing repeated NPZ loading. These technical migrations are documented in staging-migration.json and staged-source-array-loading-migration.json; they do not change the frozen training recipe. The supervisor amendment preserves selection_mode=user_initial_gen5.

## Model restoration

For each of the five research candidate directories, run `python restore_model.py` there. It verifies every 256 KiB part and the assembled bidder.keras SHA-256. Candidate 2 uses the existing ../gen5-2026-11-10 release and the same restoration script. models.json maps all six candidates to their byte counts, hashes and locations.

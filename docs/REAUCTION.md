# Retrofit real auctions to the original self-play deals

The original 10,000 games used synthetic contracts, 32 PIMC worlds, maximum
tricks, and uniform exploration within 0.125 estimated tricks. Their PIMC policy
ignored the auction. Original data remain immutable.

Reuse requires identical original cards, dealer, vulnerability, family, strain,
declarer and opening-lead constraint. Level/doubling may differ only because this
specific behavior maximized tricks. Changing declarer changes the opening leader,
dummy and information sets: matching strain alone is insufficient. This rule
must not be applied to a future auction-aware or score-oriented behavior policy.

For reusable games, `reconcile_ben_auctions.py` validates original replay, changes
public auction/contract, recalculates duplicate scores, reconstructs pre-action
observations and all labels, and validates replay again. Original trick estimates
and behavior probabilities are retained and explicitly identified as auction-blind.
Source episode/file/record identities are retained; deal-level splits do not change.
Passed-out boards contribute auction data only. The matched subset is selected
by agreement with synthetic contracts and is not representative of all auctions.

## Reproduction

Run from this branch. BEN's checkout, models and Python environment are external.
BEN (`lorserker/ben`) is GPL-3.0; its source/models are not redistributed here.
The batched collector was developed in the concurrent self-play work and extended
here with an existing-corpus input. It uses BEN's own observation encoder and
bidder network, selecting the highest-probability legal call without search.
Each neural input sees only the current bidder's hand and public auction prefix.
The archived manifest pins BEN/model/config hashes. ChatGPT/Codex assisted Max
Schireson with implementation, testing and analysis.

1. `python scripts/prepare_reauction_corpus.py --chunks ORIGINAL/chunk-* --out results/retrofit`
2. Supply a JSON `{"deal_ids": [...]}` exclusion list for the separately reserved
   200 evaluation deals, **not** the 10,000 deals deliberately being retrofitted.
3. With BEN's Python, run `scripts/collect_ben_auctions.py --ben-dir BEN --config
   NEURAL_ONLY_CONFIG --out results/retrofit/auctions --exclude-groups RESERVED.json
   --corpus results/retrofit/original-corpus.jsonl --count 10000 --batch-size 128
   --verify-scalar 128`.
4. `python scripts/reconcile_ben_auctions.py --source-index results/retrofit/source-index.json --auctions results/retrofit/auctions --out results/retrofit/reconciled`
5. With TensorFlow/NumPy, run `scripts/train_reauction_belief.py --data
   results/retrofit/reconciled --out results/retrofit/training`.

The training script compares full-auction inputs against zeroed auction inputs
with the same architecture, initial seeds, data and final-contract features.
It uses seeds 731/732/733, Dense16/Dense16 and a residual over a capacity-balanced
ownership prior; 22,676 parameters. Early stopping uses validation NLL and can
select the untrained prior. All six fits finish before test evaluation. Paired
test intervals resample whole deals, not card rows. Arbitrary suit augmentation
is disabled because it would invalidate bidding conventions. Test outcomes
must not be used to tune this experiment further.

The existing play-only tensor export omits auctions. This experiment explicitly
encodes ordered public auction calls rather than using that export unchanged.
It supports up to 64 calls and fails rather than silently truncating longer auctions.

The output `replay-required.jsonl` contains only the mismatched non-passed-out
boards. Those require fresh 32-world max-tricks play before they can join a full
auction-and-play training set. The older synthetic-contract data remain useful
as separately labeled play-only data, not as fictitious BEN-contract trajectories.

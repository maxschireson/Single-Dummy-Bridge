# Clean bidding refresh, 9 November 2026

The experiment starts from the validated 40,000-deal DDS bidder and asks whether
clean actual-play outcomes improve completed auctions. The six candidates use
25%, 50%, or 75% play-deal sampling, crossed with original-BEN KL weights 0.02
and 0.20. Each receives 2,048 attempted duplicate pairs and two PPO epochs per
batch at learning rate 1e-5. The unchanged parent is the control.

These are pilot fine-tunes, not six full retrainings. Attempted and scored sample fractions are both recorded. Missing play
contracts are completed with the clean frozen Gen3 player, so every attempted
pair can supply a reward. Every variant uses the same initialized actor,
training seed, batch budget, optimizer settings and frozen parent opponent.

## Original knowledge and representation

The original BEN corpus is absent from the recovered checkpoint. Its pretrained
weights are available. Original-BEN KL retention on newly visited observations
is therefore a practical approximation to preserving original behavior, not a
literal old/new corpus ratio. The public 193-feature/40-call BEN interface is
unchanged: own hand, dealer, vulnerability and prior public auction. Hidden
cards and terminal outcomes reach only the reward calculator. Dropout is off
and BatchNorm statistics remain frozen, as in the original bidding trainer.

The risks are forgetting conventions, changing partner expectations, and a
different distribution of auctions or contracts in the small new corpus. A
stronger retention term can reduce drift but may also suppress improvements.
Original bid imitation accuracy is a diagnostic, not the objective.

## Reward provenance

Reject every game with v4 or v4p on either partnership. Also reject the bad
policy SHA under another name. Check active players rather than every unused
bot listed in a manifest; v4b is allowed. Exported games have their file checksums
verified. Retained trajectories are legally replayed and scores checked, then
deduplicated across exports and local streams. Only root games provide outcomes;
counterfactual play branches are not extra independent bidding examples.

For a new auction, reuse clean observed trick counts only for identical cards,
dealer, vulnerability, strain and declarer. Recompute duplicate scores using
the new contract level and double/redouble status. Preserve multiple observed
trick outcomes and average IMPs *after* nonlinear scoring. This implements the
temporary v2/v3/v4b play-equivalence assumption requested by Max. It still
ignores changes in play caused by auction information and contract incentives.

Use existing DDS labels on DDS-source deals; no standalone new DDS-table job.
Following Max's instruction to play newly reached contracts, unobserved
strain/declarer combinations are played with the frozen Gen3 cardplay bot
(32 worlds, original Gen3 belief and policy) on both sides. The play process
still uses DDS internally. Both rooms are fully scored. A shared cache reuses
these trick results across variants and contract levels, preserves the first
actual auction played, model/solver identity, complete cards and legal replay.
No other strain's result is borrowed and no missing result is called a tie.

Fresh sampled auctions provide PPO behavior probabilities. Historical greedy
auction softmax scores are not misused as behavior propensities.

## Evaluation and selection (fixed before results)

All rooms and rotations of a family stay together. Existing arena validation
families are split into development (`hash % 10 == 5`) and untouched final test
(`hash % 10 == 0`). Any overlap with prior bidder training excludes a family
from held-out use. Reconstructed DDS data retain the old 40k train / 1k dev
boundary. The DDS development set has been used in the earlier campaign and is
not described as a virgin final test.

Generate greedy duplicate auctions against the frozen parent on the same
development deals for all six candidates. Report mean IMPs, family-level
standard errors and descriptive confidence intervals. Candidate comparison
uses every development family for every candidate. Missing contracts are
played, and the evaluator rejects incomplete coverage. Cached trick reuse
across auction paths remains an explicit approximation.

Choose the highest clean-play common-support development mean for the final
test, breaking ties by DDS development mean, then stronger BEN retention, then
lower play fraction. Freeze selection.json before opening test outcomes. The
test compares only that selected candidate with the unchanged parent. No
automatic deployment or promotion follows this screen. Sampling uncertainty and the trick-reuse approximation remain explicit even
if the test mean is positive.

## Commands

```bash
python scripts/prepare_bidding_refresh.py --export CLEAN_EXPORT \
  --local-run COMPONENT_RUN --local-run SUPPLEMENT_RUN \
  --dds-checkpoint RECOVERED_40K_CHECKPOINT --out RUN/data

python scripts/run_bidding_refresh.py --data RUN/data/dataset.json \
  --parent VALIDATED_40K_BIDDER.keras --anchor ORIGINAL_BEN.keras \
  --out RUN --phase train --play-root CLEAN_ARENA_RUN --play-bot 3 \
  --dds-library libbridge_dds.so

python scripts/run_bidding_refresh.py --data RUN/data/dataset.json \
  --parent VALIDATED_40K_BIDDER.keras --anchor ORIGINAL_BEN.keras \
  --out RUN --phase dev --play-root CLEAN_ARENA_RUN --play-bot 3 \
  --dds-library libbridge_dds.so
```

Training checkpoints include Adam state after every committed batch. Restarting
the same command resumes from the committed offset. Manifest hashes reject a
changed dataset, source or recipe. Final actors preserve the BEN Keras format.

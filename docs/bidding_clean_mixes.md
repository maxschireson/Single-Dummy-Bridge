# Clean bidding mix refresh — 9 November 2026

The experiment compares 25%, 50%, and 75% clean-play deal sampling, crossed
with original-BEN KL weights 0.02 and 0.20. All six candidates start from the
validated 40,000-deal DDS bidder. Each gets 2,048 duplicate training pairs.
The unchanged parent is the control. No model is automatically deployed.

## Data and representation

The frozen data contain 3,824 legally replayed clean games on 1,868 distinct
families: 1,477 train, 199 development, 192 final test. Both partnerships must
avoid v4 and v4p, including aliases of their policy hash. Existing 40k DDS
training deals and the prior 1k DDS development cache supply the other stream.
No separate new DDS-table job is needed; normal cardplay uses DDS internally.
The 1k DDS development cache was used previously and is not a virgin test.

The original BEN training corpus is absent from the recovered checkpoint;
its pretrained weights are present. KL retention on visited observations is
an approximation to preserving original bidding behavior, not literal replay
of BEN's base corpus. The 193-feature/40-call interface remains unchanged:
own hand, dealer, vulnerability and past public calls. Hidden cards enter only
the reward computation. Freeze BatchNorm moments and disable dropout.

## Exact auction rewards

Following Max's concern that play can differ within a strain, historical play
is reused only for the identical auction, oriented deal, dealer and
vulnerability. This also distinguishes levels, doubles, declarer and auction
paths reaching the same final contract. There are 1,907 observed exact auctions.
Missing auctions are played with frozen Gen3 cardplay (32 samples, clean policy
and belief) on both sides. Preserve full records and verify legal replay.

A shared cache includes the complete auction and frozen model/solver identity.
Thus every sampled and held-out pair receives a score without borrowing another
contract's tricks. Historical v2/v3/v4b games are still treated as compatible,
as Max authorized. Multiple exact historical outcomes retain their empirical
trick distribution; average IMPs after nonlinear duplicate scoring.

Fresh sampled auctions provide PPO behavior probabilities. Greedy historical
softmax scores are never misused as sampling probabilities. The earlier
same-strain approximation was stopped after 256 committed training pairs and
is not used to initialize the exact-auction experiment.

## Held-out comparison

Keep complete canonical families together, including every room and rotation.
Retain the arena's original hash%5 training boundary; half the old validation
families become development (hash%10=5), half final test (hash%10=0). Verify no
held-out family was in the starting bidder's recovered training data.

All candidates bid greedily against the frozen parent on all development deals,
with partnerships swapped between rooms. Report paired mean IMPs and
family-level standard errors. Replay missing auctions and require full coverage.
Choose the highest clean-play development mean; break ties by DDS development
mean, stronger BEN retention, then lower play fraction. Freeze selection.json
before testing only that chosen variant on the final 192 clean families.
Selection-set rankings are exploratory; final-test uncertainty remains visible.

## Runtime and reproducibility

Use configs/bidding_exact_mixes.json: minibatch 64, learning rate 2.5e-6,
two PPO epochs, exploration 0.005. The smaller batch and proportionately lower
learning rate reduce memory demand while keeping the rough update budget per
example comparable to the initial 256 / 1e-5 recipe. Every candidate shares the
same settings, initial weights, seed and frozen opponent.

Two earlier combined training/play processes were terminated with exit 137.
The exact run separates auction collection, cardplay and gradient updates
into three processes per batch, disables oneDNN, and checkpoints model and Adam
state after every batch. Pending observations and RNG state are persisted so
recovery retains the same on-policy decisions. Each gradient stage loads the
compressed arrays once and slices that one allocation. Its supervisor lock
prevents duplicate pipelines. Resume rejects changed
source, data, initialization or recipe hashes. Model actors remain BEN-compatible
Keras files.

```bash
python scripts/prepare_bidding_refresh.py --export CLEAN_EXPORT \
  --local-run COMPONENT_RUN --local-run SUPPLEMENT_RUN \
  --dds-checkpoint RECOVERED_40K_CHECKPOINT --out INITIAL_RUN/data
python scripts/prepare_exact_bidding_outcomes.py --source INITIAL_RUN/data \
  --out RUN/data
python scripts/bidding_refresh_pipeline.py --data RUN/data/dataset.json \
  --parent VALIDATED_40K_BIDDER.keras --anchor ORIGINAL_BEN.keras \
  --out RUN --play-root CLEAN_ARENA_RUN --dds-library libbridge_dds.so
```

The supervisor completes all six mixes, runs development, freezes the selected
variant and runs its final test. It never deploys a candidate or overwrites arena
models. Full model/data/source hashes and raw per-board comparisons are retained.

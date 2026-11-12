# Initial belief training and independent BEN calibration

Max's updated direction, 8 November 2026: start with a small belief model,
condition on bidding as well as play, generate evaluation data concurrently with
training, and use BEN to bid contracts that our engine then plays.

The independent 10,000-complete-deal collection audit passed on 8 November
2026. Max subsequently authorized starting the first small model. The initial
fit is explicitly play-only; real bidding-aware training still needs BEN data.

## Data streams and separation

- Keep the existing 10,000-deal collection and its original train/validation/test
  groups intact. Its synthetic auctions carry no hand evidence; it supports
  play-only experiments, not realistic bidding inference.
- For subsequent combined data, let a pinned BEN version bid all four seats,
  supplying each bidder only its own hand and the public auction. Freeze the
  resulting complete auction and contract before our PIMC bot plays all seats.
  Preserve BEN version, model/config hashes, system settings, dealer,
  vulnerability, every call and actual hidden-hand labels separately from inputs.
  Passed-out boards are valid bidding examples, but are not complete 52-card-play
  games and must be reported separately.
- Auction-only data can be generated independently of expensive card-play data.
  Begin with an engineering budget of 50,000–100,000 independent auctions, then
  use learning curves to choose the next collection budget. The current BEN
  adapter can supply the auctions; its optional search makes actual throughput
  something to measure, not assume.
- Keep a fixed validation set for architecture selection and early stopping.
  Generate a separately seeded test batch while training, reserving its deal
  hashes before observing outcomes. Training and evaluation may run concurrently
  with bounded CPU workers; they must never share original deals or deal families.
  Persist excluded deal/group hashes and check every subsequent training import.
- A batch inspected to choose models is development data thereafter. Use fresh,
  untouched test deals for the final strength claim. Compare all frozen candidates
  on the same batch; do not keep collecting until significance happens to appear.
  A later, predeclared batch is legitimate when the first result is inconclusive.
- Keep BEN-calibration records permanently excluded from training. Each run writes
  its original-deal hashes to manifest.json. Distinct seeds are provenance, not a
  substitute for checking actual hashes. Seat/suit variants retain their group's
  exclusion; suit changes must preserve bidding-system semantics.

## First model

Start around 100,000 parameters (later compare roughly 30,000 and 300,000).
The first executable baseline uses ordered card/seat embeddings flattened into
a small MLP, preserving order while keeping CPU training/inference cheap. The
planned bidding-aware successor can use small recurrent encoders for calls and
card play, followed by shared state features and ownership/shape heads. These are experimental sizes,
not established sample-complexity thresholds. Around 8,000 training deals do not
become independent merely because they provide hundreds of thousands of positions.

Train hidden-card ownership cross entropy, optionally with remaining suit lengths
and high-card points as auxiliary targets. Mask facts already determined by hard
knowledge. Enforce legal joint deals during sampling. Track likelihood/calibration
and actual card-play strength; a marginal-probability improvement alone is not a
strength result. Include bidding-system context and evaluate generalization to
other opponents as the dataset expands. For an auction-prefix example, future
calls and the eventual contract are unavailable; play examples may see the full
completed auction. True hidden hands remain targets only.

Use the existing synthetic-play corpus as an explicitly separate play-only source.
Do not attach a newly generated auction to an old trajectory played under a
different contract. The existing NPZ v1 tensors omit auctions; a bidding-aware
training encoder must add call/seat sequences from the preserved JSON and version
that schema before fitting a combined model.

## BEN card-play calibration

Freeze BEN's auction once per independently generated deal. At table 1 our PIMC
bot plays North/South against BEN East/West; at table 2 the partnerships swap on
the identical deal, contract, vulnerability and auction. Each player chooses its
own opening lead. Both sides receive legal observations only. This measures card
play under BEN auctions, rather than comparing bidding systems.

Initial calibration: 200 reserved deals, four predeclared shards of 50, deal seeds
20261201–20261204 and decision seeds 23001–23004. Our settings remain batch PIMC,
32 sampled worlds per non-forced decision, expected tricks, uniform selection
within 0.125 estimated tricks. BEN uses the pinned portable neural/DDS setup,
with its own native sample/search settings unchanged. This is an as-configured
comparison, not an equal-compute comparison; record both engines' time.

Report paired tricks/board, IMPs/board, deal-cluster confidence intervals,
failures and passed-out boards. Replay every complete record and verify settings,
unique original deals, and disjointness from the self-play collection. The small
initial batch is a baseline estimate; modest gains will require a larger fresh
batch (for example 1,000–2,000 deals) chosen before inspecting its results.

BEN revision: 9b5f43104aeac713a80b73513f2f2d6daf9f8769. Its portable configuration
disables BBA, BGA PIMC, ACE and SuitC; results do not represent every BEN setup.
Our bot maximizes tricks while BEN is configured for IMPs, so report tricks and
IMPs separately. The current sampler ignores bidding evidence whereas BEN uses
it; this is part of the current performance gap that a belief model aims to close.

## Commands

Run one calibration shard (repeat with independent seeds and ports for parallel
servers; large BEN processes require a memory budget):

```sh
python3 scripts/ben_integration.py --ben-dir ../ben --ben-python ../ben-venv/bin/python \
  --count 50 --deal-seed 20261201 --decision-seed 23001 --port 8091 \
  --samples 32 --objective tricks --near-tie 0.125 --out results/ben-calibration/chunk-0
```

For future training collection, use fresh deals excluded from all evaluation
registries and an already-running BEN server:

```sh
python3 -m bridge_harness generate --count 10000 --seed 20261301 --out data/ben-source.jsonl
python3 -m bridge_harness freeze-auctions data/ben-source.jsonl data/ben-frozen.jsonl \
  --ben-url http://127.0.0.1:8085
python3 -m bridge_harness.selfplay --corpus data/ben-frozen.jsonl --count 10000 \
  --samples 32 --near-tie 0.125 --objective tricks --workers 4 --out data/ben-selfplay
```

These existing commands perform bidding followed by PIMC play; they do not fit a
model. Audit complete played games separately from passed-out auctions. Do not
include bulk games, archives, model files or logs in Git.


## Executable first baseline

`bridge_harness/belief_model.py` and `scripts/train_belief.py` implement a
90,856-parameter observation-only play baseline (default hidden widths 80/64).
A fixed ordered embedding of cards and seats preserves sequence positions;
this initial version uses an MLP rather than a recurrent network. Loss is
ownership cross entropy over uncertain hidden cards only. Support masks remove
impossible owners. No privileged target, future result, behavior policy or
example identifier enters the encoder.

The training script verifies the 10,000-deal audit and original grouped split
counts, records input file hashes, uses only validation NLL for early stopping,
and never evaluates test labels. The selected checkpoint is compared with
uniform legal ownership and an approximate capacity-balanced marginal prior.
The latter is a diagnostic baseline, not an exact uniform feasible-deal sampler.
`--residual-prior` learns corrections to that prior and starts from zero
correction; `--augment` applies consistent seat rotations and suit permutations
to play-only observations and targets. Those permutations must not be applied
blindly to real bidding conventions. Learned marginals still need a legal joint
deal sampler before they can guide PIMC; this script does not deploy a bot.

TensorFlow is optional for the harness; the first run used TensorFlow 2.21.0.
To reproduce the regularized baseline from the complete dataset archive:

```sh
python scripts/train_belief.py --data /path/to/extracted-dataset \
  --audit /path/to/extracted-dataset/audit-10000.json \
  --out results/belief-small-v2 --epochs 20 --patience 4 --threads 4 \
  --residual-prior --augment
```

A saved `.keras` file contains raw logits (residual logits with
`--residual-prior`). Read its accompanying manifest and add the observation-only
log capacity prior before applying the hard support mask and softmax. Preserve
all model/data/schema provenance. The first-run report records both the initial
unregularized attempt and the subsequent correction; neither is a strength claim.


## Fast hand-dependent auction collection

Max approved weaker, faster bidding for training data. Use BEN's neural-only
configuration (`bidding.search_threshold=-1`,
`bidding.check_final_contract=False`, `sampling.no_samples_when_no_search=True`),
with the pinned portable external models and BBA disabled. The collector batches
independent public-prefix requests of equal length, selects the best legal
neural call and skips search, DDS, rescue bidding and auxiliary hand inference.
This changes the bidding policy relative to full-search BEN; it is explicitly
identified as `BEN-neural-only-batched`. It is not a claim of equal strength.

`scripts/collect_ben_auctions.py` reserves original deal hashes before bidding,
requires an exclusion registry, records source/model/config hashes and grouped
splits, independently validates complete auctions and stores privileged full
hands separately from public transcripts. All 10,000 original play deals,
200 reserved calibration deals and 1,000 development auctions were excluded
from the 50,000-auction collection. Passed-out auctions remain valid belief
examples and are reported separately; no auction is counted as a complete
52-card-play game.

`scripts/prepare_auction_belief.py` audits all auctions and constructs four
completed-auction views plus one sampled pre-call view for each seat per deal.
The input function accepts only own hand, observer, dealer, vulnerability and
public prefix. It accepts neither a full board nor future calls/contract.
Ownership targets are separate, seats are relative to the observer, and all
views of a deal retain its original split. No future call is supplied to a
prefix example.

`scripts/train_auction_belief.py` fits a roughly 47,000-parameter baseline with
ordered call/seat embeddings and a small MLP. It early-stops on validation NLL,
keeps test metrics untouched, and checks a validation ablation with auction
information removed. This is auction-only pretraining; combined bidding/play
training needs newly played trajectories under these actual contracts.

A future mixture can include other neural or rules-based bidding systems, with
source/system identifiers in the model input. A single BEN-style data source
cannot demonstrate generalization to human conventions or other systems.

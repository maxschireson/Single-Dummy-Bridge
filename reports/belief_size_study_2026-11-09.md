# Two belief sizes for the next bridge bot

Max requested an early size comparison using all currently available auction
and play data, including completed evaluation trajectories. Mixed versions and
opponents are pooled; source metadata is retained, not used as an exclusion.
This experiment is separate from the frozen v2 and DDS bidding workers.

The candidates jointly condition on own original hand, the public auction,
visible remaining hands, ordered public play, voids, remaining capacities and
public contract context. They predict the owners of uncertain remaining cards.
Bidding-only rows contain no invented play. Older synthetic auctions are masked
on play-training rows. Hidden cards are labels only; future plays, selected
future actions, scores and DDS results are not inputs.

| Candidate | Dense widths | Parameters |
|---|---|---:|
| Small | 64, 64 | 80,054 |
| Large | 256, 128 | 308,726 |

The 46,582-parameter auction parent is expanded with zero weights for public
play inputs. Balanced neuron replication and zero-sum outgoing perturbations
widen the larger network without changing initial predictions. Both candidates
start from the same predictive function. The NumPy player export is checked
against TensorFlow; a new explicit `PublicBeliefPlayer` factory leaves existing
frozen bots unchanged.

## Frozen-data pilot

- Original 50,000 BEN-auction corpus, keeping its original splits.
- Audited DDS training export at 40,000 independent deals, containing 58,002
  distinct room auctions. Bidding confirmation/development boards are excluded.
- Original completed play training and currently complete v2 self-play records.
- Completed policy/belief, three-engine/BEN and sample-budget evaluation records.
  Repeated trajectory copies are deduplicated. Different trajectories on the
  same deal are retained within one split and do not count as independent deals.
- Sixteen deterministic positions spread through each play trajectory. Positions
  with no uncertain owners are omitted from loss. All source files are hashed,
  so more positions can be exported later without replaying any games.
- Existing held-out assignments are preserved. A registry records former
  evaluation families used in training; these are retired as independent
  benchmarks for the new candidates. Subsequent play-strength tests use fresh
  deals. No new DDS calls or play collection are required for this fit.

Both sizes get the same files, eight pilot epochs, row ordering, seed 2026110902,
AdamW learning rate 0.0002, weight decay 0.0001, gradient clip 1, dropout 0.15,
batch size 1024, and one CPU training thread. The selectable parent/epoch zero
is retained. The predeclared checkpoint score is 50% public-play validation
ownership NLL, 25% completed-auction DDS-bidding validation NLL and 25%
completed-auction BEN validation NLL. Domain results are also reported separately.
This weighting is a working choice for the pilot, not a strength/promotion gate.

The fit saves selected and latest model **and Adam** checkpoints after every
epoch, refuses concurrent writers, and verifies data/source hashes on resume.
Bounded invocations stop after an epoch; invocation duration is not a change
to the fixed epoch budget. Active training time is reported separately.

Example commands, with local source locations supplied explicitly:

```sh
python scripts/prepare_belief_size_study.py --bidding-data /path/to/audited/export \
  --parent /path/to/auction-parent.npz --sources /path/to/sources.json --out runs/size-study/data
python scripts/train_belief_size_study.py --data runs/size-study/data \
  --out runs/size-study/small --size small --run-seconds 240
python scripts/train_belief_size_study.py --data runs/size-study/data \
  --out runs/size-study/large --size large --run-seconds 240
```

`sources.json` is a list of `{ "path": "/path/to/episodes", "role": "training" }`
or `retired-evaluation` entries. It also accepts a JSONL file of complete records.
The final dataset manifest, rather than the changing source directories, defines
the exact data used by both fits.

## Continuation and promotion

Keep both candidates until the remaining play data is available. Compare
validation ownership NLL, accuracy and Brier score, learning curves, inference
cost and fresh downstream play at identical sampling budgets. Data from related
model versions/opponents remains pooled by default. Prediction improvement is
not automatically an IMP improvement.

After choosing the architecture/training recipe and deciding to promote, a
separate fixed-recipe refit can include the current held-out evaluation data.
Preserve the evaluated checkpoint and record the refit as a different artifact.
Use fresh deals for the next independent comparison, rather than reporting
training-set performance as a held-out result.

Validation so far: 13 focused existing/new tests passed, including observation
privacy, relative-seat rotation, ownership support/masks, function-preserving
widening and NumPy/TensorFlow export equivalence. Fit results will be appended
when both candidates complete; no improvement or promotion is claimed at setup.

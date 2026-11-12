# Two belief sizes for the next bridge bot

The **308,726-parameter candidate leads the 80,054-parameter candidate on all
three held-out ownership-prediction domains** after the same eight-pass pilot.
Its public-play ownership accuracy is 55.66% versus 55.38% for the smaller net
and 54.41% for the starting model. The gain is modest and consistent; both
candidates and their Adam states are preserved for the remaining play data.
These are prediction results, not measured IMP or playing-strength gains.

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

## Completed pilot results

The frozen corpus contains **963,304 training observations** and **121,362
validation observations**. Play records cover 19,586 distinct deals: 15,468
training, 1,974 validation and 2,144 reserved test. Both auction sources retain
their prior splits. No test labels were used for fitting or model selection.
The play training/validation pool includes 9,001 original-play trajectories,
6,589 current-v2 trajectories, and 4,910 prior-evaluation trajectories, after
trajectory deduplication. Different trajectories on one deal are correlated.
1,692 former evaluation training families are recorded as retired benchmarks.

| Measure | Starting model | Small | Large |
|---|---:|---:|---:|
| Public-play NLL, lower better | 0.698851 | 0.695413 | **0.694354** |
| Public-play ownership accuracy | 54.41% | 55.38% | **55.66%** |
| Public-play Brier, lower better | 0.492033 | 0.488967 | **0.488026** |
| BEN completed-auction NLL | 1.053766 | 1.052941 | **1.051778** |
| DDS-bidding completed-auction NLL | 1.053569 | 1.052648 | **1.051588** |
| Selected epoch / completed epochs | 0 | 6 / 8 | 6 / 8 |
| Active fit time | — | 231.81 s | 357.95 s |
| Neural inference, batch 1 | — | 0.0197 ms | 0.0397 ms |

The NLL table weights uncertain-card labels equally. Paired comparisons below
first average within a deal family; this different weighting explains small
point-estimate differences. Negative values favor the larger network.

| Validation domain | Deal groups | Large minus small NLL | Descriptive 95% interval |
|---|---:|---:|---:|
| DDS-bidding complete auctions | 3,983 | -0.001040 | [-0.001137, -0.000943] |
| BEN complete auctions | 5,023 | -0.001163 | [-0.001254, -0.001071] |
| Public play | 1,971 | -0.001254 | [-0.001608, -0.000900] |

Three play-validation deals supplied no uncertain-card targets. Intervals are
paired descriptive normal intervals after checkpoint selection, not independent
final-test evidence. Bidding-source belief validation reserves families from
bidding TRAIN data; it is not an end-to-end bidding evaluation.

On the same public-play observations, uniform legal-owner NLL is 0.718454 and
the capacity-balanced prior is 0.708251. Both learned models beat these simple
baselines as well as their shared starting model. Neural inference is a small
CPU microbenchmark with one BLAS thread; it does not measure whole-bot speed.
The larger model costs about 0.020 ms extra per neural call in this environment.
It used about 54% more active training time, while both saw the same eight
passes over the frozen data. These timings exclude preparation and downtime.

The larger net is the provisional preference for continuation. Preserve both
until the remaining v2 play data is ready, then compare on the new held-out
play observations before selecting the next fit. No bot was replaced by this
pilot, and no new DDS calls or games were needed to train it.

Both sizes passed NumPy/TensorFlow export checks (maximum absolute errors below
4e-7). Thirteen focused tests passed, and a stopped tiny fit resumed through a
second epoch with its optimizer checkpoint. Runtime: Python 3.12.14, TensorFlow
2.21.0, NumPy 2.5.4. Exact hashes, provenance, selected/latest model and Adam
checkpoints, and frozen arrays are in the recovery archive.

[Download both resumable candidates and their frozen data](https://chatgpt.com/library?file_id=libfile_fde3_f-2eeccefff2348191b1578aeae86c19d7_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).

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

The existing DDS bidding run remains parked at exactly 40,000 pairs. This
belief pilot did not modify its model, optimizer, DDS cache or promotion gates.

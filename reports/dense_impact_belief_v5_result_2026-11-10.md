# Dense v5 belief: final result

The selected candidate is epoch 2 of the 308,726-parameter dense v4 architecture,
warm-started from the selected v4 weights and Adam state. It was trained with
card-level ownership cross-entropy weighted by cross-fitted DDS information
value. The attention experiment remained paused throughout. No reserved test
family was prepared or evaluated, and this model was not promoted to the arena.

## Verdict

Epoch 2 narrowly beat unchanged v4 on the frozen composite validation objective,
0.86761349 versus 0.86795576 (lower is better), a reduction of 0.00034226 or
0.039%. The recent policy-clean play slice improved weighted NLL by 0.00025825,
but the family-cluster standard error was 0.00036310 across 192 families. That is
only 0.71 standard errors and is not convincing evidence of a real improvement.

The most directly consequential subset did not improve: NLL on the 1,687
upweighted validation-card targets rose from 0.75468581 to 0.75535006, a
regression of 0.00066424. Ordinary recent-play NLL and accuracy improved slightly,
so the composite win looks like a small broad fine-tuning gain rather than proof
that consequence weighting made the important-card predictions better.

## Validation metrics

| Domain | Metric | v4 / epoch 0 | selected v5 / epoch 2 | v5 minus v4 |
| --- | ---: | ---: | ---: | ---: |
| Recent clean play | ordinary NLL | 0.67132578 | 0.67106467 | -0.00026111 |
| Recent clean play | consequence-weighted NLL | 0.67280401 | 0.67254576 | -0.00025825 |
| Recent clean play | upweighted-card NLL | 0.75468581 | 0.75535006 | +0.00066424 |
| Recent clean play | accuracy | 60.0982% | 60.2797% | +0.1815 pp |
| Recent clean play | Brier | 0.46787222 | 0.46760039 | -0.00027183 |
| Historical play | NLL | 0.69360386 | 0.69331390 | -0.00028997 |
| Historical play | accuracy | 55.6325% | 55.7539% | +0.1214 pp |
| Historical play | Brier | 0.48804426 | 0.48777347 | -0.00027079 |
| Historical bidding | NLL | 1.05334479 | 1.05294368 | -0.00040111 |
| Historical BEN | NLL | 1.05207036 | 1.05165063 | -0.00041973 |
| Frozen composite | score | 0.86795576 | 0.86761349 | -0.00034226 |

Recent metrics cover 47,004 uncertain-card validation targets in 3,063 positions
from 192 usable families. The upweighted subset has 1,687 targets. Historical
validation comprises 494,951 public-play targets in 2,075 families, 895,752
bidding targets in 3,983 families, and 783,588 BEN targets in 5,023 families.

## Epoch selection

| Epoch | Composite score | Recent weighted-NLL delta vs v4 | Cluster SE | Fit time |
| ---: | ---: | ---: | ---: | ---: |
| 0 (v4) | 0.86795576 | 0 | — | — |
| 1 | 0.86769613 | -0.00009172 | 0.00032917 | 37.5 s |
| 2 | **0.86761349** | **-0.00025825** | 0.00036310 | 36.1 s |
| 3 | 0.86764933 | -0.00002239 | 0.00038515 | 54.7 s |

## Data and timing

The clean recent pool was frozen before training. It merged policy-clean records
by canonical family, retaining 4b and excluding every trajectory in which either
partnership used the bad v4/4p policy. The frozen pool contained 1,411 training,
193 validation and 186 reserved-test families. Of these, 1,408 training and 192
validation families produced usable uncertain-card positions.

The fit used 998,425 positions and 31,120,476 uncertain-card training targets
across 89,652 training families. That includes 975,958 recovered historical
positions plus 22,467 recent clean positions. Recent training contributed
345,490 card targets, including 11,413 consequence-upweighted targets. Recent
validation contributed 3,063 positions and 47,004 targets, including 1,687
upweighted targets. Historical replay contains less data than the full original
v4 fit, while the v4 starting weights retain what that larger fit learned.

Consequential-card labeling took 1,326.5 seconds. Baseline evaluation, three
epochs, validation and export took about 143 seconds; the three fit epochs
themselves totaled 128.3 seconds. End-to-end wall time was about 24.7 minutes.

## Artifact verification

The selected NumPy export SHA256 is
`2ce3e0145363b62daacf86afde43a3c39fb8a7af7c94d7d721b08bb148545236`.
The trainer's export check found maximum absolute logit error
`3.58e-7`. An independent restore of the selected epoch-2 TensorFlow optimizer
checkpoint and comparison over 512 validation rows found maximum error
`5.96e-7`. The selected checkpoint contains 9,106 Adam optimizer iterations.

The result is worth preserving as a candidate, but the experiment did not show
that emphasizing consequential cards improved consequential-card ownership
accuracy. It should not replace v4 on this evidence alone.

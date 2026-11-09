"""Publish the frozen scalar/distribution experiment without selecting on test."""
import argparse
import json
from pathlib import Path
import shutil
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from scripts.train_policy_choices import family_summary,choose
from bridge_harness.loop_registry import sha


def report(run,out):
    out.mkdir(parents=True,exist_ok=True)
    data=json.loads((run/'data/dataset.json').read_text())
    scalar=json.loads((run/'fit/result.json').read_text())
    dist=json.loads((run/'distribution-fit/result.json').read_text())
    # Ensure the parallel fit's choice evaluation used the final scalar model.
    if (run/'fit/result.json').stat().st_mtime > (run/'distribution-fit/training.json').stat().st_mtime:
        raise ValueError('Verify scalar comparator was final before distribution choice evaluation')
    with np.load(run/'distribution-fit/test-choice-predictions.npz',allow_pickle=False) as z:
        pred={k:z[k] for k in z.files}
    root=(pred['depth']==0)&pred['current_policy'].astype(bool)
    labels=[('gen3','Gen3 outcome policy'),('gen4','Gen4 IMP-difference policy'),
        ('rank','IMP-weighted ranking repair'),('scalar','New scalar outcome fit'),
        ('expected_tricks','New distribution: expected tricks'),
        ('expected_imps','New distribution: self-reference IMPs'),
        ('contract_imps','New distribution: contract-made reference')]
    def delta(key,mask):
        gain=(choose(pred[key+'_contrast'][mask])-choose(pred['gen3_contrast'][mask]))*pred['y'][mask]
        return family_summary(gain,pred['group'][mask])
    def interval(s):return 'n/a' if s['ci95'] is None else f"[{s['ci95'][0]:+.4f}, {s['ci95'][1]:+.4f}]"
    rows=[]
    for key,label in labels:
        metrics=dist['held_out_choices']['root'][key]
        gain=delta(key,root)
        rows.append(f"| {label} | {100*metrics['decisive_accuracy']['mean']:.2f}% | {metrics['regret_to_better_recorded_move']['mean']:.4f} | {gain['mean']:+.4f} | {interval(gain)} |")
    primary=dist['held_out_choices']['root']['expected_imps_minus_gen3']
    scalar_gain=scalar['held_out_choices']['root']['new_minus_gen3']
    fresh=dist['held_out_choices']['fresh_root']['expected_imps_minus_gen3']
    root_stats=dist['held_out_choices']['root']['expected_imps']
    scalar_test=scalar['test_outcomes'];dist_test=dist['test_outcomes']
    counts=data['counts']
    modeldir=ROOT/'models/cardplay/outcome-policy-2026-11-09';modeldir.mkdir(parents=True,exist_ok=True)
    for name,src in [('scalar.npz',run/'fit/best.npz'),('distribution.npz',run/'distribution-fit/best.npz')]:
        shutil.copy2(src,modeldir/name)
    for label,folder in [('scalar','fit'),('distribution','distribution-fit')]:
        for name in ('result.json','config.json','training.json'):
            shutil.copy2(run/folder/name,out/(label+'-'+name))
    shutil.copy2(run/'data/dataset.json',out/'dataset.json')
    shutil.copy2(run/'distribution-fit/test-choice-predictions.npz',out/'test-choice-predictions.npz')
    text=f'''# Outcome-trained policy and trick distribution — 2026-11-09

This experiment restores individual outcome prediction and compares a scalar
trick evaluator with a categorical trick distribution. Neither candidate is
trained on IMP differences. No arena model was replaced.

Neither candidate establishes an advantage over Gen3. The scalar retrain has
the larger point estimate: **{scalar_gain['mean']:+.4f} IMP per audited mainline
decision**, descriptive family-clustered 95% interval **{interval(scalar_gain)}**.
The primary distribution readout returns **{primary['mean']:+.4f}**, interval
**{interval(primary)}**. These are offline comparisons of two recorded moves,
not estimates of full-game IMPs per board.

## Frozen data

| Partition | Deal families | Outcome rows |
|---|---:|---:|
| Train | {data['families']['train']:,} | {counts['outcomes_train_rows']:,} |
| Validation / checkpoint selection | {data['families']['validation']:,} | {counts['outcomes_validation_rows']:,} |
| Held-out test | {data['families']['test']:,} | {counts['outcomes_test_rows']:,} |

There are {data['total_families']:,} canonical families, {counts['trajectories']:,}
complete trajectories, and {counts['ordinary_outcome_rows']+counts['forced_outcome_rows']:,}
individual outcome labels. Of these, {counts['forced_outcome_rows']:,} are forced
alternative cards. Each trajectory contributes up to 16 newly executed eligible
positions, always including its forced alternative. Replayed prefixes are omitted;
completed continuations are legally replayed and their scores checked. All rooms,
positions and descendants of a family remain in one partition. Families with
no eligible positions do not contribute to prediction metrics.

Sources are the complete local supplemental and component arenas at the frozen
snapshot. The remote training feed supplies IMP contrasts but lacks individual
trick outcomes and the full search features needed for this recipe; it is not
silently counted as outcome training data. The Gen3 initialization retains the
earlier learning. Older raw training rows were not replayed in this fine-tune.

The hash-modulo-ten partition preserves the original 80/20 train/holdout boundary,
with buckets 0 and 5 reserved for test and validation. Total gradient weight is
equal per family. Multiple dependent positions are not independent boards.

## Training

Both candidates start from the same Gen3 checkpoint and use visible cards,
ordered public play, the auction, contract/vulnerability, and the existing PIMC
estimates. Hidden hands, future cards, outcomes and identifiers are excluded.
Both retain the current PIMC near-tie candidate filter (0.125 tricks), keeping the
comparison with Gen3 controlled. They do not yet test IMP-aware plays that this
trick-based candidate filter excludes.

- **Scalar:** unchanged {scalar['parameters']:,}-parameter architecture; predict
  actual remaining partnership tricks for the played/forced card using squared
  error. All layers train. Selected epoch {scalar['selected_epoch']} of 8 by
  validation-family MSE; epoch zero was eligible.
- **Distribution:** {dist['parameters']:,} parameters; 14 probabilities for remaining
  partnership tricks, with impossible counts masked. The Gen3 scalar estimate
  initializes a discrete Gaussian, with zero-initialized state/action categorical
  residual heads and a trainable global spread. Train categorical cross entropy;
  selected epoch {dist['selected_epoch']} of 8 by validation-family negative log
  likelihood. No choice or IMP metric selects either checkpoint.

AdamW uses learning rate 0.0002, weight decay 0.0001 and gradient clipping at 1.
Batch size is 128. The first scalar attempt was killed before finishing an epoch;
the fit restarted from Gen3 with smaller batches and oneDNN disabled. Both final
fits use the same complete frozen dataset. Exported NumPy inference agrees with
TensorFlow within {scalar['numpy_max_error']:.3g} (scalar values) and
{dist['numpy_max_error']:.3g} (probabilities).

## Scoring distributions

The **primary IMP readout** first identifies the network's own expected-trick
choice, then freezes that move's predicted outcome distribution as the reference
for every candidate. Tied expected-trick choices contribute an equal mixture.
Each candidate is scored by averaging IMP(score(candidate outcome) minus
score(reference outcome)) across the two distributions. Contract, vulnerability,
doubles and redoubles enter exact bridge scoring.

The product of the marginal probabilities defines a virtual comparison table;
it does not claim to capture correlations between two lines on the same hidden
deal. A move compared with its own distribution has zero expected IMPs.
The fixed-contract-making reference is retained only as a prespecified diagnostic.

A regression check covers the user's hopeless doubled-contract example: when
the reference is 99% down one, the self-reference objective protects the
undertrick against an unjustified gamble for making. The fixed-making reference
can reverse that preference in the constructed example.

The same probabilities also expose a **matchpoint readout**: probability of a
better duplicate score plus half the probability of a tie, using the same frozen
reference distribution. This is a starting point, not a field-calibrated or
full-game-validated matchpoint player.

## Held-out move choices

The primary sample contains {root_stats['gain_over_recorded_reference']['rows']:,}
mainline disagreements over {root_stats['gain_over_recorded_reference']['families']:,}
families, including {root_stats['decisive_rows']:,} nonzero outcomes.
Accuracy is averaged within decisive families, then across families equally.
Regret and gain use all audited disagreements, including zero swings.

| Scorer | Better-move accuracy | IMP regret to better recorded move | IMP gain vs Gen3 | 95% interval for gain |
|---|---:|---:|---:|---|
{chr(10).join(rows)}

Earlier held-out families were previously examined for the separate ranking
experiment. On families added after that experiment's snapshot, the primary
distribution readout gains {fresh['mean']:+.4f} IMP per decision, interval
{interval(fresh)}, across {fresh['families']:,} families and {fresh['rows']:,}
mainline choices. This subset was not used to change training or select a model.

## Held-out prediction

| Measure | Gen3 / initial distribution | New model |
|---|---:|---:|
| Scalar trick MSE | {scalar_test['gen3_mse']:.6f} | {scalar_test['new_mse']:.6f} |
| Distribution mean trick MSE | {dist_test['gen3_mean_mse']:.6f} | {dist_test['mean_mse']:.6f} |
| Distribution negative log likelihood | {dist_test['initial_gaussian_nll']:.6f} | {dist_test['nll']:.6f} |

The distribution's probability loss improves relative to its initialization,
while its mean-trick error worsens. The NLL baseline is Gen3's mean wrapped in the declared initial Gaussian;
Gen3 itself did not output a categorical distribution. Prediction improvements
must not be treated as proof of better action choices.

## Limits and artifacts

Continuation policies were frozen mixed bots. These fits forecast their observed
outcomes, not optimal future play. Recorded comparisons label two moves; an
unaudited third move has no measured counterfactual outcome. Admission to fork
collection was compute-budget limited. Confidence intervals cluster by canonical
family and are descriptive; they do not correct for comparisons across variants.
Full-game evaluation on fresh families is required before promotion.

- [Scalar weights](../../models/cardplay/outcome-policy-2026-11-09/scalar.npz)
- [Distribution weights](../../models/cardplay/outcome-policy-2026-11-09/distribution.npz)
- [Scalar results](scalar-result.json)
- [Distribution results](distribution-result.json)
- [Frozen dataset manifest](dataset.json)

The frozen encoded dataset is preserved as
[Outcome_Policy_Training_Data_2026-11-09.zip](https://chatgpt.com/library?file_id=libfile_fde3_f-22ef5bd53ac88191867de52f7905ade9_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).
Reproduce with `prepare_outcome_policy.py`, `train_outcome_policy.py`,
`train_distribution_policy.py`, and `report_outcome_policy.py`, supplying the
frozen source runs and checkpoint paths. `mixed_arena.selector` recognizes
distribution checkpoints in this experimental branch; no running arena changed.
'''
    (out/'README.md').write_text(text)
    print(json.dumps(dict(primary=primary,fresh=fresh,report=str(out/'README.md'),
        model_sha256={p.name:sha(p) for p in modeldir.glob('*.npz')})))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();report(a.run,a.out)

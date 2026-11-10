# Fresh global-choice evaluation: 256 boards

This is a fixed fresh test of the frozen first DDSD corrector, the deployed V5
policy selector, and the global PIMC maximum. It follows the initial historical
fork study. It does not retrain or promote a model.

## Why new continuations

The earlier study could compare only the two cards with recorded continuations.
Its PIMC baseline was the better of those two cards, even when a third legal
card had a higher PIMC value. This experiment explicitly chooses the global
PIMC maximum and plays out the alternatives actually selected by each method.

The additional local legacy records contain 12 clean unseen test families but
no unused fork comparisons on those families. Single-continuation records are
still sufficient for outcome-residual training; new paired continuations are
needed to expand the direct choice-quality test.

## Frozen protocol

- Reserve 256 independently drawn deals using seed 202611106617, all in the
  canonical cardplay test bucket. Exclude every prior corrector family. These
  new families remain evaluation-only.
- Freeze current Gen5 neural-only auctions. One board passes out.
- Play a base trajectory with frozen Gen5 policy and belief, 32 sampled deals
  per nonforced decision and a 0.125-trick candidate window.
- Select one nonforced decision uniformly within each of three phases: plies
  0–19, 20–39, and 40–51. Selection is independent of predictions, disagreement,
  hidden-card configuration and outcome. A phase with no nonforced decision is
  omitted.
- At each selected position, draw the same 32 worlds for every method. Compare
  global PIMC best, V5 best inside the normal global window, and DD plus the
  fixed weight-one corrector best inside that window. Use a shared random
  ordering for exact score ties.
- Play each distinct selected card to completion with the same frozen Gen5
  continuation players. Streams are keyed by board, ply and controller.
  Reuse the base continuation when a method selects the base card.
- Include agreement decisions as zero gains. Compute each board's mean audited
  decision gain, then average boards equally. Report paired standard errors
  across boards. This is IMP per audited decision, not whole-agent IMP/board.

Both networks receive their normal information at the choice point. The
corrector sees each sampled hidden layout; neither chooser receives the true
hidden hands. True-deal DD and full-hand inputs are used only in secondary
prediction diagnostics after the choices have been fixed.

The primary comparison is corrector versus global PIMC. V5 versus PIMC and
corrector versus V5 are reported alongside it. Secondary prediction diagnostics
use the selected cards, so they do not represent an independent random sample
of all legal actions. Exact PIMC ties and non-tie overrides are reported
separately.

## Interpretation

This cohort is fresh and uses current Gen5 continuation play. The initial
corrector was trained on older clean continuation policies; this tests its
transfer to Gen5. Results are kept separate from the historical-fork cohort.
No weights, correction coefficient, candidate window, target size or selection
rule are adjusted in response to these results.

The complete records include every base and branch action, final scores,
predictions, chosen cards, and source/model/corpus hashes. The first four boards
were checked for legal complete replay, matching prefixes, and the global
PIMC maximum before continuing the fixed block. V5 predictions also match the
production player to 1e-6 on five independently re-evaluated positions.

## Reproduction

`scripts/prepare_ddsd_fresh.py` uses the TensorFlow bidder to reserve and bid
fresh deals. `scripts/evaluate_ddsd_fresh.py` uses NumPy/PyTorch and DDS to
collect the fixed cohort, checkpointing each completed board. It resumes from
the existing manifest and rejects modified source, models or corpus.
`scripts/analyze_ddsd_fresh.py` legally replays the records and adds prediction
diagnostics. Models and their hashes are recorded in `evaluation-manifest.json`.

The frozen source, summaries and completed records are retained with the pilot.


## Completed results

All 256 reserved boards finished (255 played, one passed out), with 765 audited
decisions, 551 additional continuations and 806 complete legal tables replayed
by the verifier. At 477 decisions at least two methods chose different cards;
50 decisions produced unequal final trick outcomes among the selected choices.
The collection pass after the four-board check took about ten minutes with two
workers. No configuration was adapted after seeing outcomes.

| Comparison | IMP per audited decision | SE | 95% interval |
|---|---:|---:|---:|
| V5 minus global PIMC best | +0.09804 | 0.06060 | [−0.02074, +0.21682] |
| Corrector minus global PIMC best | −0.00915 | 0.03660 | [−0.08088, +0.06258] |
| Corrector minus V5 | −0.10719 | 0.05287 | [−0.21082, −0.00356] |

The primary test provides no evidence that the corrector improves on PIMC.
V5 is ahead of the corrector by 2.03 paired standard errors on this cohort;
that secondary contrast is modest evidence, not a whole-agent strength result.
In tricks per decision, the corrector gains +0.00654 (SE 0.00774) versus PIMC,
and V5 gains +0.00261 (SE 0.01031). The differing trick and IMP rankings reflect
which contracts were affected and the small number of unequal outcomes.

V5 changed 341 exact PIMC ties and overrode a strictly higher PIMC value on 39
other decisions. The corrector changed 343 ties and made only four non-tie
overrides; all four finished with the same outcome as the PIMC branch. Thus
this first corrector is functioning predominantly as a tie-breaker. These
counts compare actual selected cards under the shared tie ordering; they do
not use half credit against a tied baseline.

Summing local audit gains, V5's tie changes contribute +75 IMPs and +11 tricks;
its 39 non-tie overrides contribute zero IMPs and −9 tricks. The corrector's
tie changes contribute −7 IMPs and +5 tricks, with zero from its four non-tie
overrides. These sums describe overlapping local counterfactual comparisons,
not a board or match score. The slice breakdown is exploratory.

### Secondary prediction diagnostics

These evaluate the policy-selected candidate cards on each audited decision.
Each decision gets equal weight within a board, and each board equal weight.

| True-deal outcome predictor | MSE |
|---|---:|
| Actual-deal DD | 0.241176 |
| DD + full-hand corrector | 0.233362 |
| DD + hidden-ownership-masked control | 0.234019 |

Full-hand minus control MSE is −0.000657, SE 0.001723: no demonstrated gain from
explicit hidden ownership. Full-hand versus DD reduces MSE by 0.007814,
SE 0.004640. The primary question remains action-specific improvement, not
absolute calibration.

For the three fixed policy-pair contrasts at each selected decision (including
zero contrasts where choices coincide), sampled PIMC difference MSE is 0.065610,
corrector MSE is 0.065375, and V5 MSE is 0.071095. Corrector minus PIMC is
−0.000234, SE 0.000226, again inconclusive. V5 minus PIMC is +0.005485,
SE 0.002172. Better contrast calibration is not sufficient to infer better
contract-sensitive play; the actual IMP choice test above remains primary.

The prototype has not earned Gen 6 promotion. Current-generation retraining or
better learning of action-specific hidden-hand effects remains a research
step; this experiment alone cannot distinguish those explanations.

[Data, frozen weights and complete continuations](https://chatgpt.com/library?file_id=libfile_fde3_f-92806d46076c8191a97cedf19c89a832_cf78a91e4b8c81918243c2c17fc9b8b9&account_id=personal).

# Consistent strategy experiments

This adds an independently written implementation of the alpha-mu search ideas
of Tristan Cazenave and Véronique Ventos, with Pareto-front optimization ideas
from their subsequent work with Swann Legras. See `CREDITS.md` for bibliographic
and license details. No alpha-mu implementation code was imported.

## What is implemented

`strategy.AlphaMu` searches weighted related layouts with declarer and dummy
fixed. Each result contains an outcome vector and an executable policy witness.
Declarer chooses one card across an information set. Public defender cards
select subsequent observation branches. At defender nodes the search combines
branch policies and takes each world's worst legal defensive reply. Dominated
vectors are removed after each combination; memoization shares identical
subproblems. Unknown/inactive worlds use a neutral coordinate during combination.

With `max_plies=None`, a completed search is exact **on its supplied finite world
set, among deterministic declarer policies, against omniscient best defence**.
It does not solve information-limited partnership defence, prove that the sample
covers all plausible layouts, or compute an equilibrium with randomized policies.
The objective can be expected final tricks, contract success, or duplicate score.
Weights are normalized; duplicate particles are merged with their probability
mass preserved. Input validation rejects duplicate cards, impossible counts,
changed declarer/dummy hands, inconsistent public states and invalid weights.

`max_plies=N` counts declarer/dummy card plays and uses DDS at the horizon. Such a
result is labelled non-executable when its selected policy contains a DD leaf.
It retains strategy fusion beyond that horizon. At depth one its value agrees
with PIMC. It is an upper relaxation of the same omniscient-defence game, **not**
a general upper bound on performance against ordinary defenders. Budget limits
raise `SearchLimit` instead of returning an incomplete front as exact.

The implementation includes dominance pruning, incremental front products and
memoization. It does not yet implement all early/root cuts or redundant-world
optimizations from the papers. Python and policy-witness storage also make this
a correctness/reference implementation, not a speed reproduction of their work.

## Full-hand executable plans

`rollout.PolicyPlanner` optimizes a bounded number of nonforced declarer choices
against fixed information-limited defender policies, then plays every candidate
to terminal using an explicit continuation policy. It averages actual terminal
scores, with no double-dummy replacement of the tail. Fixed defender models
permit scalar conditional expectations; these are distinct from alpha-mu's
adversarial vector backups.

A plan is a map from complete permitted observations to cards, plus a fallback.
Both the continuation and the defender model can use `greedy` or `pimc` through
`ViewPolicy`. PIMC continuations draw fresh hypotheses from their own allowed
view; their inner decision evaluation remains approximate, but executing that
policy produces achievable results. Policy seeds and caches depend on the view,
never on the outer world identity. West sees West and dummy, not South's fixed
outer sample. Full-history replay validates supplied rollout worlds.

By default, the `strategy` harness player uses two nonforced choices with a
greedy tail and greedy defender model. CLI options `--strategy-decisions`,
`--strategy-continuation`, `--strategy-model` and `--strategy-policy-samples`
configure these. The `continuation` player executes exactly the same fallback
without the planning prefix, providing a matched ablation. It plans once at its first nonforced declarer decision,
then commits to that policy for the hand. Unanticipated observations use the
same advertised fallback. It does not silently replan and claim that a fixed-tail
value measures a different deployed policy. This deliberately modest tail can
limit playing strength severely; the purpose is an executable baseline.

The `alphamu` harness player uses ordinary PIMC earlier (using the same observation-dependent random stream as the PIMC
control) and attempts complete
alpha-mu search once at most three cards per hand remain. Its default two-second
search budget falls back to PIMC explicitly if exhausted. It follows a completed
policy while observations remain supported. An out-of-support observation is
logged and causes a new solve or PIMC fallback; a prior sample value is not a
promise for such an observation. Both new players are declarer-only. The runner
resets stateful players between tables.

Beliefs currently use the existing hard-constraint sampler. Neither auction
likelihoods nor likelihoods of earlier discretionary defender plays are included.
An eight-particle sample, in particular, is not a complete belief distribution.

## API example

```python
from bridge_harness.core import Contract
from bridge_harness.strategy import AlphaMu, Position

# Each Position holds sorted remaining hands in N/E/S/W order, current leader,
# optional current trick, and declarer's already-won trick count.
solver = AlphaMu(Contract(3, "N", 2), objective="make")
result = solver.solve(worlds, weights)  # terminal search, no DD horizon
print(result.value, result.stats)
policy_json = result.best.policy.to_dict()
```

Two small generated fixtures in `tests/fixtures/` preserve a root-choice failure
and an unresolved-guess valuation gap. They are regression examples, not bulk
experiment logs. The test suite also verifies that budget fallback restores the
PIMC random stream, and that stateful players reset between paired tables.

## Reproduce

```sh
python3 scripts/build_dds.py
python3 -m unittest discover -s tests -v
python3 scripts/benchmark_strategies.py endings --count 1000 --cards 3 \
  --samples 8 --seed 620001 --out results/alpha_mu_1000.jsonl
python3 scripts/benchmark_strategies.py matches --count 100 --samples 8 \
  --seed 730001 --candidate strategy --out results/strategy_fullhand_100.jsonl
python3 scripts/benchmark_strategies.py matches --count 100 --samples 8 \
  --seed 730001 --candidate alphamu --out results/alphamu_coupled_100.jsonl
python3 scripts/benchmark_strategies.py endings --count 100 --cards 4 \
  --samples 8 --seed 630001 --out results/alpha_mu_4card_100.jsonl
python3 scripts/benchmark_strategies.py matches --count 100 --samples 8 \
  --seed 740101 --candidate strategy --baseline continuation \
  --continuation pimc --decisions 1 --out results/strategy_pimc_tail_100.jsonl
```

Small-ending families hold North/South fixed while varying East/West. Half use
two suits to exercise more interacting card combinations; half use all suits.
Strains cycle across NT and all four trump suits. The reference metric is final
tricks; each generated three-card ending starts with ten declarer tricks.
Consequently this is a synthetic tactical test, not a representative frequency
estimate for real bridge. PIMC root ties in this benchmark are deterministic;
full-hand PIMC uses the harness's seeded random tie breaking.

The ending benchmark separately measures: (1) optimism in the best PIMC value,
(2) loss caused by its chosen root action **allowing optimal consistent play
after that action**, and (3) exact strategy execution against every defensive
reply in every sampled layout. This separates valuation error from move error.

Full-hand paired trials use the same deals, fixed opening lead and common greedy
defenders, with synthetic assigned contracts. They measure this configuration,
not tournament strength. Raw generated deals, per-decision logs and binaries
remain excluded from Git; the report retains summaries and reproduction seeds.

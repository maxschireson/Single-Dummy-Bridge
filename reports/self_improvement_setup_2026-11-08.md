# Self-improvement process checkpoint — 8 November 2026

Implemented a resumable controller on top of the existing three-engine and
self-play code. This is preparation for the final v2; no production learning
cycle, new BEN strength comparison, scheduled task, or cloud worker was started.

## Available

- Immutable bot/weight registration and source/native-solver pins.
- Cumulative 10k → 50k → 250k self-play collection, frozen real auctions,
  independent-deal split/overlap checks, bounded workers and restartable games.
- A trainer request/result interface and reference warm-start auction-belief
  trainer; the final combined belief/policy trainer remains a v2 binding.
- Same-deal partnership-swapped comparisons against original, parent and BEN,
  plus parent versus BEN to measure the paired improvement in the BEN matchup.
- Multiplicity-adjusted IMP promotion gates, immutable promotion history,
  unchanged-weight detection, failure blocking, and progress Markdown/JSON.
- Effect-size/variance-based arena sizing. Model validation uses approximately
  10% of collected independent deals; arena size is not fixed at 10% of training.

The gate requires a credible improvement over the parent and improvement in the
BEN matchup, not necessarily an outright win over BEN. It stops after the largest
training stage if no candidate qualifies. Accepted candidates become v3/v4/…;
older bots remain available. All comparisons keep bidding frozen and measure
card play. The existing v2 evidence is not reclassified as a confirmed IMP gain.

## Validation

- Built the native DDS shared library successfully.
- Final full suite: **68 tests run, 66 passed, 2 skipped**, 22.24 seconds.
  Both skips require optional TensorFlow.
- All **18 loop tests passed**, including the real DDS complete-game test
  through the frozen auction-weighted factory.
- The end-to-end process test runs cumulative 4/8-deal synthetic collection,
  subprocess trainer handoff, two evaluation sizes, report generation, and
  repeated resume. Completed game timestamps remain unchanged. Synthetic
  campaigns are explicitly labelled and cannot promote production bots.
- Tested both promotion endpoints, improvement while still losing to BEN,
  rejection of duplicate deals/tampered scores/artifacts, source/config gates,
  writer exclusion, retained failures and explicit retries, all-tie behavior,
  unchanged-weight arena skipping, and quadratic effect-size scaling.
- `git diff --check` and Python compilation passed.

These are process/correctness tests, not playing-strength results. The fixture
trainer submits a fixed simple player and does not learn. The weighted DDS test
uses zero model weights, not the final v2 checkpoint. TensorFlow is unavailable
in this setup runtime, so the optional reference fitter was source/compile
checked but not executed. Its network/optimizer code reuses the existing
auction-belief architecture and loss.

## Binding still required before launch

Finalize and freeze v2's selected inference factory, all belief/policy weights,
and its actual training command; bind the genuine-auction collector and verified
full-search BEN endpoint/config/models. Use the BEN calibration/prior pilot's
paired IMP standard deviations and a target gain to choose the arena budget
before looking at new candidate outcomes. The 2k/8k/32k ladder is provisional.

The prepared recipe intentionally refuses launch with missing bindings. The
reference auction-only trainer is not a substitute for the pending policy work.
Strong play changing trajectories can create new policy/play-aware learning
signal; with a fixed bidder, auction-only ownership labels do not improve merely
because the card player became stronger.

See [the runbook](../docs/SELF_IMPROVEMENT.md) and
[configuration template](../configs/self_improvement.json) for exact commands,
trainer interface, statistical assumptions, runtime costs and restart behavior.

Source and concise reports are versioned. Generated deals, raw match logs,
weights, SQLite state and compiled binaries are excluded from Git.

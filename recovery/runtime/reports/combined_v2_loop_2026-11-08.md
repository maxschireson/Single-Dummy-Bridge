# Combined v2 self-improvement launch — 2026-11-08

Requested: put both belief and policy networks into v2, use neural-only BEN
bidding, start iteration, and favor progress per elapsed time.

The combined bot runs the existing auction-weighted 32-sample PIMC and uses the
published policy selector within its 0.125-trick near-tie window. Evaluation is
greedy; self-play mixes 20% uniform exploration within that window and logs exact
probabilities. Both learners warm-start the parent; epoch zero remains eligible.
The baseline original v1 is uniform PIMC. BEN's card-play search stays enabled.

The first generation collects 10k deals, then cumulatively 50k/250k if needed.
Training retains the deal-level 80/10/10 split. Changed candidates first screen
against their parent on 1k paired deals; positive candidates receive BEN
confirmation at 250/1k/4k deals. Same-deal parent versus BEN games are cached
across data stages. Promotions require both adjusted statistical gates. The
smaller confirmation cap trades sensitivity to small gains for more iterations.

## Verification

- Minimal bidder reproduced all 32 archived BEN auctions/contracts checked.
  Batched and scalar greedy output agreed; only the bidder model was loaded.
- Combined v2 played 30 complete real-auction games with replay/legality checks.
  Collection took 39.2 seconds with four workers during the integration check;
  this small measurement is not a sustained throughput forecast.
- Both networks completed a one-epoch end-to-end training smoke test (9.75s).
  Both correctly retained epoch-zero weights when validation worsened.
  NumPy policy export matched TensorFlow within the asserted tolerance.
- Full suite: 77 tests passed, including the TensorFlow checks.
- Tests cover logged behavior propensities, support restrictions, screening
  without BEN, cohort and parent/BEN cache reuse, exclusions, resume, promotion,
  immutable artifacts, information boundaries, and scoring.

These checks establish execution and data integrity, not a playing-strength
improvement. No v3 promotion or positive IMP result is claimed at launch. The
policy sees public play/state and auction-informed PIMC values, not a new direct
auction embedding. See docs/SELF_IMPROVEMENT.md for the protocol and commands.

The published belief and policy studies retain their separate evidence and
limitations. Imported selector code is credited to the repository's self-play
study commit f26f975a5c197def5e203dd2da87d84dd54aadb9. BEN/DDS models and raw data
remain external to this source-only PR. Assistance: OpenAI Codex with Max
Schireson.

# Independent Gen 8 cutover — 12 November 2026

Max's [opened Gen 8 handoff](https://github.com/maxschireson/Single-Dummy-Bridge/blob/695078457205693f48a24c355681aef47ca21935/docs/gen8_candidate_2026-11-12.md)
supersedes this collector's Gen 7.1 comparison and conditional self-play gate.
The [combined recipe](../../configs/round8-independent.json) keeps the two
opened plans' relative weights: 25% standard Gen 8 versus Gen 7.1, and 12.5%
each Precision Gen 8 versus Gen 7.1, Precision versus standard Gen 8,
standard versus Gen 5RZ32, Gen 1, BEN16 and BEN64. No other collector changed.

The predecessor drained without failures at **3,293 independent completed
boards**, preserving its manifest, models, episodes, receipts and dashboard
results. Its final feed revision is
[`cbddecbc290efc8e3ab6e088135675df1cec14e5`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/cbddecbc290efc8e3ab6e088135675df1cec14e5).
The successor manifest is `d7632508f164f642df727e677ef2976efe25697559205b8078114e606abc3f07`,
frozen source `6776c28a3d94746b10ed841adf7f7050e822a6b3`, feed
[`arena-gen8-independent-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-independent-feed).
Its 7,816 families are exactly unused predecessor families, with zero overlap
against completed predecessor records, the model owner's 34,029 training
families, or the conservative 34,092-family union. The original reconstruction
and owner authority remain separate, hash-pinned files. [Corpus audit and
validation](validation.json) record the hashes and actor identity checks.

Gen 8 retains policy v4.1 and the standard 32-sample tree settings, adds the
released system-aware scorer and reading from trick 1, and has a second actor
using the released Precision r4 bidder. All baseline actor specifications are
unchanged. Gap capture and tie-audit budgets, honest propensities, legal replay,
common/native conditions and BEN16/64 weights/effort are preserved. Exported
replay tables retain their declared system labels; play, bidding and total
views were checked against the exact raw record values. Recovery now includes
the external rule JSON files, and changing the pinned trick-estimate bytes
prevents resume. The dashboard describes Gen 8 using the frozen feed's model
note and retains historical Gen 7.1 results.

Validation: 65 targeted tests passed, one optional neural-adapter test skipped
because source-path house bidders were not restored. The initial broader run
had two errors in the new external-file pinning path for an empty estimate;
that case was fixed and the affected suite plus a tamper-rejection regression
passed. Real-model preflight exercised all seven scheduled pair types. Six
pairs through the generic runner checked native/common rooms, legal replay,
tree arithmetic and budgets; separate BEN16/64 checks verified configured
budgets were reached, with smaller compatible sets allowed late in play, and
no BEN forks. The final frozen Precision comparison checked **1,182 searched
decisions and 24 gap forks**, with guess metrics and all three required system
labels. A separate exporter/recovery check verified the exact native/common
results and every pinned runtime file in the recovery capsule. Preflight
records are labelled validation artifacts, never arena boards.

These preflights establish collection correctness, not playing strength. The
shared handoff's BEN factors remain unmeasured assumptions; they were not tuned
here. No model was trained. Repository-wide generation cleanup/main integration
is separate from this host's deployment. The hourly handoff watcher stays enabled.

Initial live verification at 2026-11-12T17:54:16Z: 9 completed production families, zero failures, fresh heartbeat and held writer/watchdog locks. GitHub snapshot [`2df41bcf`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/2df41bcf4a9a694b2180dd60c092718e7120de3a) contains 6 SHA-verified family records; the dashboard reader accepted exact common/native totals and replay coverage. This is a startup observation, not a sustained throughput or strength estimate. [Launch health](launch-health.json).

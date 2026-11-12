# Branch inventory

Snapshot of 12 November 2026 ~03:10 UTC, regenerated at the Gen 6 → Gen 7 cleanup:
122 branches (78 on 11 November). Last-commit times are UTC. This is not process
monitoring: a recent commit is not proof a worker is healthy, and an old one is not proof it
is abandoned. Nothing is deleted or renamed in a cleanup; feeds, transfers, archives and
control channels are never merged into source. Feed commit messages from `ops/publish_gen5.py`
say "Gen5:" for every generation; read the branch name and manifest instead.

## Source and deployment (8)

Development and adopted source. Start from `main`.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`feature/boxctl-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/boxctl-20261112) | 11-12 01:16 | Box control agent; merged into main at this cleanup |
| [`feature/gen7-alpha-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen7-alpha-20261111) | 11-11 12:01 | Ancestor of the candidate; contained in main |
| [`feature/gen7-candidate-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen7-candidate-20261111) | 11-12 02:23 | Deployed Gen 7 source (`fe382f9b`); merged into main at this cleanup. The Gen 7 session may keep committing here |
| [`feature/gen7-prepare-slice-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen7-prepare-slice-20261112) | 11-12 03:06 | Pre-7 test tooling; sibling of the candidate, conflicts with it (backlog 5) |
| [`feature/gen8-systems-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen8-systems-20261111) | 11-11 23:57 | Gen 8 systems layer, WIP (backlog 6) |
| [`fix/gen6-feed-health-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/fix/gen6-feed-health-20261111) | 11-11 09:22 | PR #13: main-based port of capture, self-play and feed health (backlog 1) |
| [`gh-pages`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/gh-pages) | 11-12 03:03 | Live dashboard and its feed registry; own publisher |
| [`main`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/main) | 11-11 07:47 | Shared source; Gen 6 + Gen 7 after this cleanup |

## Collector runtime lineage (9)

Source that collectors ran but that is not on main. Preserve; integrate through backlog item 1.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`codex/gen6-auto-ben-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-auto-ben-20261111) | 11-11 04:45 | BEN budget auto-expansion; contained in gen6-fast-selfplay |
| [`codex/gen6-ben-followups-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-ben-followups-20261111) | 11-11 05:38 | BEN follow-up launch record |
| [`codex/gen6-data-handoff-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-data-handoff-20261110) | 11-10 19:29 | Gen 5 data index for the Gen 6 handoff |
| [`codex/gen6-fast-selfplay-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-fast-selfplay-20261111) | 11-11 09:41 | Collector runtime: fast self-play mix, capture, gap forks (backlog 1) |
| [`codex/gen6-gen7-capture-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-gen7-capture-20261111) | 11-11 05:54 | Collector runtime: capture and gap forks (backlog 1); contained in gen6-fast-selfplay |
| [`codex/gen6-independent-collector-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-independent-collector-20261111) | 11-11 03:02 | Independent Gen 6 collector launch |
| [`codex/gen6-medium-ben-correction-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-medium-ben-correction-20261111) | 11-11 02:17 | BEN share moved to medium; contained in gen6-fast-selfplay |
| [`codex/gen6-v7-capture-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen6-v7-capture-20261111) | 11-11 05:58 | Collector runtime: BEN64 follow-ups with capture (backlog 1) |
| [`ops/gen7-fast-selfplay-cloud-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/ops/gen7-fast-selfplay-cloud-20261111) | 11-11 23:28 | Cloud self-play collector runtime (backlog 1) |

## Earlier launch and collector branches (8)

Contained in main or historical; kept because manifests and recovery notes cite them.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`codex/connection-test-2026-11-08`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/connection-test-2026-11-08) | 11-08 12:17 | Add trivial file to test GitHub write access |
| [`codex/gen4-component-ablation`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen4-component-ablation) | 11-09 23:30 | Export replay-validated games excluding the Gen4 policy artifact |
| [`codex/launch-gen5-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/launch-gen5-20261110) | 11-10 04:23 | Use Gen5 at 32 against historical bots and archive initial 192 comparisons |
| [`codex/launch-gen5r-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/launch-gen5r-20261110) | 11-10 15:50 | Document coherent live arena refresh and revision-linked replays |
| [`codex/launch-gen5rz-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/launch-gen5rz-20261110) | 11-10 17:33 | Pin arena restarts to the TensorFlow virtual environment |
| [`codex/launch-gen5rz-ben-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/launch-gen5rz-ben-20261110) | 11-10 18:00 | Record live RZ trials, BEN takeover and retained compatible results |
| [`codex/launch-gen6-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/launch-gen6-20261111) | 11-11 02:43 | Gen 6 launch source; contained in main |
| [`codex/round5-ben-and-timing`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/round5-ben-and-timing) | 11-10 01:55 | Retain BEN search details and reported sample counts in arena records |

## Gen 7 feeds (2)

Producer publications for the current generation. Never merge.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`arena-gen7-phase1-azure1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure1-feed) | 11-12 03:10 | Gen5: 281 verified paired deals, common/native bidding |
| [`arena-gen7-phase1-codex-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-codex-20261112-feed) | 11-12 03:10 | Gen 7 phase 1 · Codex non-BEN collector: 99 verified deals |

## Gen 6 feeds and controller records (17)

Gen 6 publications (some still publishing self-play at this snapshot) and controller logs. Never merge.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`arena-gen6-ben-expansion-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-ben-expansion-feed) | 11-11 05:46 | Gen5: 248 verified paired deals, common/native bidding |
| [`arena-gen6-chatgpt-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-chatgpt-feed) | 11-12 02:56 | Gen6 ChatGPT: verified independent cohort snapshot and complete recovery records |
| [`arena-gen6-codex-ben-followups-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-ben-followups-feed) | 11-11 05:52 | Gen5: 217 verified paired deals, common/native bidding |
| [`arena-gen6-codex-ben-gate`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-ben-gate) | 11-11 05:21 | Record arena controller observations and recovery status |
| [`arena-gen6-codex-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-feed) | 11-11 05:16 | Gen5: 1543 verified paired deals, common/native bidding |
| [`arena-gen6-codex-v7-capture-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-v7-capture-feed) | 11-11 09:16 | Gen5: 1134 verified paired deals, common/native bidding |
| [`arena-gen6-codex-v7-cutover`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-v7-cutover) | 11-11 05:56 | Record arena controller observations and recovery status |
| [`arena-gen6-codex-v7-watch`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-v7-watch) | 11-11 11:58 | Record arena controller observations and recovery status |
| [`arena-gen6-extra-selfplay-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-extra-selfplay-feed) | 11-12 02:27 | Additional Gen6 fast self-play: arena and complete Gen7 training recovery snapshot |
| [`arena-gen6-fast-selfplay-20261111-19bbdce5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-20261111-19bbdce5-feed) | 11-12 03:09 | Gen5: 4722 verified paired deals, common/native bidding |
| [`arena-gen6-fast-selfplay-cloud-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-cloud-feed) | 11-12 02:24 | Gen7 cloud self-play: 1672 boards and full recovery snapshot |
| [`arena-gen6-fast-selfplay-codex-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-codex-20261111) | 11-12 02:43 | Gen6 fast self-play: 3710 verified deals |
| [`arena-gen6-fast-selfplay-independent-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-independent-feed) | 11-12 03:09 | Gen5: 9694 verified paired deals, common/native bidding |
| [`arena-gen6-fast-selfplay-primary-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-primary-feed) | 11-11 12:05 | Gen5: 2020 verified paired deals, common/native bidding |
| [`arena-gen6-gen7-capture-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-gen7-capture-feed) | 11-11 07:54 | Gen5: 725 verified paired deals, common/native bidding |
| [`arena-gen6-independent-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-independent-feed) | 11-11 02:15 | Gen5: 81 verified paired deals, common/native bidding |
| [`arena-gen6-medium-ben-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-medium-ben-feed) | 11-11 05:10 | Gen5: 1424 verified paired deals, common/native bidding |

## Earlier feeds (10)

Gen 1–5 publications. Never merge.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`arena-components-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-components-feed) | 11-10 03:48 | Update Gen 4 component feed: 2803 completed boards |
| [`arena-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-feed) | 11-09 22:58 | Update arena dashboard: 2228 paired boards |
| [`arena-gen5-codex-32-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen5-codex-32-feed) | 11-10 14:16 | Gen5: 6607 verified paired deals, common/native bidding |
| [`arena-gen5-codex-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen5-codex-feed) | 11-10 04:18 | Gen5: 45 verified paired deals, common/native bidding |
| [`arena-gen5r-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen5r-feed) | 11-10 17:33 | Gen5: 2552 verified paired deals, common/native bidding |
| [`arena-gen5rz-ben-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen5rz-ben-feed) | 11-11 02:03 | Gen5: 8372 verified paired deals, common/native bidding |
| [`arena-gen5rz-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen5rz-feed) | 11-10 17:44 | Gen5: 151 verified paired deals, common/native bidding |
| [`arena-local-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-local-feed) | 11-10 00:37 | Update ChatGPT Gen 4 feed: 3454 completed boards |
| [`arena-primary-components-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-primary-components-feed) | 11-09 22:59 | Publish Gen4 hybrid mix: 1873 completed hands |
| [`arena-recovery-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-recovery-feed) | 11-10 03:41 | Finalize Gen4 archive: all 4869 completed records and frozen training provenance |

## Control channels (10)

Box control and coordination. Never merge.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`box/azure1/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure1/control) | 11-12 03:09 | boxctl: queue 20261112T030925Z-868861-phase1-status for box azure1 |
| [`box/azure1/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure1/status) | 11-12 03:09 | boxctl status azure1 2026-11-12T03:09:31Z |
| [`box/azure2/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure2/control) | 11-12 03:09 | boxctl: queue 20261112T030928Z-047745-phase1-status for box azure2 |
| [`box/azure2/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure2/status) | 11-12 03:09 | boxctl status azure2 2026-11-12T03:09:52Z |
| [`box/azure3/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure3/control) | 11-12 03:09 | boxctl: queue 20261112T030930Z-179510-phase1-status for box azure3 |
| [`box/azure3/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure3/status) | 11-12 03:09 | boxctl status azure3 2026-11-12T03:09:55Z |
| [`box/azure4/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure4/control) | 11-12 03:09 | boxctl: queue 20261112T030932Z-252586-phase1-status for box azure4 |
| [`box/azure4/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure4/status) | 11-12 03:10 | boxctl status azure4 2026-11-12T03:10:02Z |
| [`box/coordination`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/coordination) | 11-12 03:06 | Board shared by Claude sessions using the Azure boxes; allocation table |
| [`fleet/azure`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/fleet/azure) | 11-12 03:07 | Azure fleet operator: experiment queue, status, messages |

## Transfers (14)

Dataset and model handoffs with restore instructions.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`transfer/dds-bidding-40000-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/dds-bidding-40000-20261110) | 11-10 20:38 | Publish exact 40K bidding DDS training deals and 1K development set |
| [`transfer/gen3-resume-3701`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen3-resume-3701) | 11-09 08:00 | Test watchdog recovery through verified independent launcher |
| [`transfer/gen3-training-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen3-training-feed) | 11-09 22:55 | Training snapshot-0019: upload 6/6 |
| [`transfer/gen6-candidate-bidder-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen6-candidate-bidder-20261111) | 11-11 00:33 | Add Gen 6 candidate bidder release (graded alternatives) |
| [`transfer/gen6-launch-package-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen6-launch-package-20261111) | 11-11 02:05 | Gen 6 doc: final layout-selection numbers; add the test's records |
| [`transfer/gen7-capture-forks-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-capture-forks-20261111) | 11-11 05:35 | Gap forks and guess-size logging, as applied on collectors |
| [`transfer/gen7-prototype-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-prototype-20261111) | 11-12 02:24 | Gen 7 build session save points |
| [`transfer/graded-alternatives-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/graded-alternatives-20261110) | 11-10 22:10 | Add graded-alternatives bidder experiment (candidate Gen 6 bidder) |
| [`transfer/non-v4-policy-play-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/non-v4-policy-play-20261109) | 11-09 23:43 | Add verified pre-Gen4 model training tensors and 9000 raw PIMC games |
| [`transfer/pre7-test-azure1-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure1-20261112) | 11-12 02:53 | pre7-test: g7s-vs-g6f-01, 538 episodes |
| [`transfer/pre7-test-azure2-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure2-20261112) | 11-12 03:03 | pre7-test: pre7-7s-vs-6f-azure2, 363 episodes |
| [`transfer/pre7-test-azure3-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure3-20261112) | 11-12 03:03 | pre7-test: pre7-7s-vs-6f-azure3, 374 episodes |
| [`transfer/pre7-test-azure4-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure4-20261112) | 11-12 03:03 | pre7-test: pre7-7s-vs-6f-azure4, 362 episodes |
| [`transfer/v4-worker-standby`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/v4-worker-standby) | 11-09 13:25 | Add safe second-chat standby instructions |

## Archives (1)

Preserved excluded observations.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`archive/gen6-fast-ben-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/archive/gen6-fast-ben-20261111) | 11-11 02:42 | 13 accidental fast-vs-BEN16 games, excluded from scores |

## Research and experiments (43)

Snapshots; adoption is established only by a release, a plan or main.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`experiment/ace-ben-timed-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/experiment/ace-ben-timed-20261110) | 11-10 02:14 | Add resumable calibration data snapshots and recovery instructions |
| [`experiment/gen5r16-comparisons-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/experiment/gen5r16-comparisons-20261110) | 11-10 18:36 | Report completed 100-board Gen5R16 and Gen5RZ16 comparisons |
| [`experiment/gen5rz-ben192-16-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/experiment/gen5rz-ben192-16-20261110) | 11-10 17:51 | Run local fixed 100-board 5RZ-192 versus BEN-16 cardplay match |
| [`experiment/representative-pool-tuning-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/experiment/representative-pool-tuning-20261110) | 11-10 21:24 | Add paired representative-pool size screen with independent reference reuse |
| [`research/auxiliary-auction-play-10000`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/auxiliary-auction-play-10000) | 11-08 17:37 | Test ownership learning from same-deal auctions and original unrelated-contract play |
| [`research/belief-lab-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/belief-lab-20261110) | 11-10 15:50 | Record user-requested research pause and resumable state |
| [`research/belief-plus-approx-dds-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/belief-plus-approx-dds-20261109) | 11-09 21:55 | Complete belief+ and budgeted DDS screen on 200 held-out deals |
| [`research/belief-size-comparison`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/belief-size-comparison) | 11-09 01:44 | Link preserved large belief continuation checkpoint |
| [`research/belief-v5-attention-screen`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/belief-v5-attention-screen) | 11-09 22:27 | Record measured v4 fit time and dense versus attention CPU training throughput |
| [`research/belief-v5-impactful-cards`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/belief-v5-impactful-cards) | 11-10 03:28 | Promote selected dense v5 belief component by user authorization |
| [`research/bidding-actual-outcomes`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/bidding-actual-outcomes) | 11-09 11:36 | Publish all three Gen 4 candidates with training notes and resumable actual-outcome bidder |
| [`research/bidding-clean-mixes-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/bidding-clean-mixes-20261109) | 11-10 06:26 | Complete six-way clean bidding development comparison; retain selected Gen5 bidder |
| [`research/bidding-structure-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/bidding-structure-20261110) | 11-10 20:16 | Preserve bidding experiment execution across chat turns with persistent supervisor |
| [`research/clean-policy-v5-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/clean-policy-v5-20261110) | 11-10 01:11 | Promote clean attention policy as the v5 policy component |
| [`research/consistent-strategies-alpha-mu`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/consistent-strategies-alpha-mu) | 11-08 13:44 | Negative result; not adopted |
| [`research/dds-bidding-loop`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/dds-bidding-loop) | 11-08 23:50 | Link preserved raw 40k review results |
| [`research/dds-value-quick-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/dds-value-quick-20261109) | 11-09 22:43 | Train compact DDS value net and screen search cost tradeoffs |
| [`research/ddsd-corrector-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/ddsd-corrector-20261110) | 11-10 16:56 | Review Gen5 policy overrides against recorded PIMC-best alternatives |
| [`research/direct-pairs-current`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/direct-pairs-current) | 11-09 10:26 | Hide learning-by-generation dashboard until enough evidence accumulates |
| [`research/gen4-components`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen4-components) | 11-10 00:10 | Allow complete component export inventory through 10000 boards |
| [`research/gen4-local-supplement`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen4-local-supplement) | 11-09 20:58 | Retain expensive native DDS calls for later training and proof replay |
| [`research/gen6-bidding-refresh-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen6-bidding-refresh-20261110) | 11-10 19:35 | Start Gen6 bidder refresh on 1513 audited new deal families |
| [`research/gen6-current-recipe-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen6-current-recipe-20261110) | 11-10 23:24 | Include final audit and packager source in match archive |
| [`research/gen6-policy-69k-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen6-policy-69k-20261110) | 11-10 19:24 | Test 69K versus 99K attention policies from matched initialization and data |
| [`research/gen6-policy-width96-full1513-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen6-policy-width96-full1513-20261110) | 11-10 21:08 | Document wider attention comparison and validation boundary |
| [`research/gen6-system-aware-policy-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen6-system-aware-policy-20261111) | 11-11 00:07 | Prepare optional Gen6 bidding-system context and fail-closed training provenance |
| [`research/hand-fit-scorer-v1a-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/hand-fit-scorer-v1a-20261111) | 11-11 21:38 | Packaged v1a scorer, not adopted (backlog 7) |
| [`research/imp-policy-draft`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/imp-policy-draft) | 11-09 01:41 | Add direct auction policy bootstrap and random recursive IMP audits |
| [`research/joint-auction-belief-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/joint-auction-belief-20261110) | 11-11 02:06 | Add layout-selection test results to the play report (research prototype) |
| [`research/large-belief-play-test`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/large-belief-play-test) | 11-09 00:17 | Promote larger belief net on validation predictions; add cached mixed play |
| [`research/layout-embedding-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/layout-embedding-20261110) | 11-10 07:50 | Complete independent 200-deal large-position sampling evaluation |
| [`research/mixed-fork-generations`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/mixed-fork-generations) | 11-09 03:56 | Add conditional 10k decision point before successor training |
| [`research/multiscore-16-32-64`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/multiscore-16-32-64) | 11-09 05:31 | PR #9 (backlog 10) |
| [`research/outcome-policy-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/outcome-policy-20261109) | 11-09 21:26 | Publish outcome-trained scalar and distribution models with held-out results |
| [`research/pimc-study-2026-11-08`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/pimc-study-2026-11-08) | 11-08 13:46 | Archive PIMC and alpha-mu experiments with larger cost study |
| [`research/policy-branch-ranking-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/policy-branch-ranking-20261109) | 11-09 19:30 | Evaluate Gen4 branch choices and train family-held-out IMP-weighted ranking policy |
| [`research/primary-component-diagnosis`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/primary-component-diagnosis) | 11-09 19:16 | Stop primary v4 self-play and freeze component diagnostic allocation |
| [`research/reauction-existing-10000`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/reauction-existing-10000) | 11-08 17:16 | Retrofit BEN auctions to 10000 deals and report matched-subset belief experiment |
| [`research/self-improvement-loop`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/self-improvement-loop) | 11-08 22:32 | Verify process handoff preserves saved collection records |
| [`research/selfplay-training-2026-11-08`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/selfplay-training-2026-11-08) | 11-08 22:00 | Report completed 1000-deal policy increment over belief-informed PIMC |
| [`research/shared-beliefs-dds-cache`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/shared-beliefs-dds-cache) | 11-08 23:54 | PR #4 (backlog 9) |
| [`research/three-engine-play-200`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/three-engine-play-200) | 11-08 18:06 | Compare baseline, bidding-informed PIMC and BEN on the same 200 deals |
| [`research/v4-belief-and-arena`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/v4-belief-and-arena) | 11-09 11:00 | Train additive v4 belief and preserve resumable model and paired uncertainty results |

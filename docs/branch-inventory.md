# Branch inventory

Snapshot of 12 November 2026 ~18:15 UTC, regenerated at the Gen 7 → Gen 8 cleanup:
270 branches (122 at the Gen 6 → Gen 7 cleanup fifteen hours earlier). Last-commit times are UTC. This is not process
monitoring: a recent commit is not proof a worker is healthy, and an old one is not proof it
is abandoned. Nothing is deleted or renamed in a cleanup; feeds, transfers, archives and
control channels are never merged into source. Feed commit messages from `ops/publish_gen5.py`
say "Gen5:" for every generation; read the branch name and manifest instead.

## Source and deployment (13)

Development and adopted source. Start from `main`.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`docs/generation-cleanup-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/docs/generation-cleanup-20261112) | 11-12 03:13 | The Gen 6 → Gen 7 cleanup; merged (PR #14) |
| [`feature/boxctl-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/boxctl-20261112) | 11-12 01:16 | Box control agent; on main since the Gen 6 → Gen 7 cleanup |
| [`feature/gen7-alpha-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen7-alpha-20261111) | 11-11 12:01 | Ancestor of the Gen 7 candidate; contained in main |
| [`feature/gen7-candidate-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen7-candidate-20261111) | 11-12 02:23 | Deployed Gen 7.0 phase 1 source (`fe382f9b`); on main since the Gen 6 → Gen 7 cleanup |
| [`feature/gen7-prepare-slice-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen7-prepare-slice-20261112) | 11-12 03:13 | Pre-7 test tooling; conflicts with main in twelve files (backlog 5) |
| [`feature/gen7-selfplay-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen7-selfplay-20261112) | 11-12 06:51 | Gen 7 self-play regime, the Gen 7.1 notice; merged into main at this cleanup (`5099000`) |
| [`feature/gen8-p41-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen8-p41-20261112) | 11-12 16:14 | Policy 4.1 session: the reading bench and `scripts/check_feed_families.py`; not on main |
| [`feature/gen8-prototype-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen8-prototype-20261112) | 11-12 16:47 | Deployed Gen 8 source (`792c4cb`, the commit that opened the plans) and its later page commits; merged into main at this cleanup. The Gen 8 session may keep committing here |
| [`feature/gen8-systems-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen8-systems-20261111) | 11-11 23:57 | First draft of the Gen 8 systems layer (one commit); superseded by the layer that came onto main with Gen 8 |
| [`fix/gen6-feed-health-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/fix/gen6-feed-health-20261111) | 11-11 09:22 | PR #13: feed-health supervision; conflicts with main (backlog 1) |
| [`fix/gen7-selfplay-capture-codex-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/fix/gen7-selfplay-capture-codex-20261112) | 11-12 04:44 | PR #15: gap and guess capture kept in self-play; Codex's Gen 7.0 self-play cohort ran it; conflicts with main in `bridge_harness/gen5_arena.py` (backlog 1) |
| [`gh-pages`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/gh-pages) | 11-12 18:05 | Live dashboard and its feed registry (84 sources: 18 Gen 6, 53 Gen 7, 13 Gen 8); own publisher |
| [`main`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/main) | 11-12 03:13 | Shared source; Gen 6, Gen 7 and Gen 8 after this cleanup |

## Collector runtime lineage (15)

Source that collectors ran. The Gen 8 ones are on main; what is not is in backlog item 1.

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
| [`codex/gen7-independent-selfplay-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen7-independent-selfplay-20261112) | 11-12 04:48 | Independent collector, Gen 7.0 self-play cutover (`168d580`); one commit not on main, conflicts in `ops/prepare_gen7_alpha.py` (backlog 1) |
| [`codex/gen7-phase1-independent-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen7-phase1-independent-20261112) | 11-12 03:28 | Independent collector, Gen 7.0 phase 1 (`522eda6`); contained in main |
| [`codex/gen71-independent-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen71-independent-20261112) | 11-12 15:04 | Independent collector, Gen 7.1: `--exclude-families`, the promotion gate, the training-family audit; Azure's Gen 7.1 ran it at `a588e09`; merged into main at this cleanup (`b09c865`) |
| [`codex/gen8-independent-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/codex/gen8-independent-20261112) | 11-12 17:54 | Independent collector, deployed Gen 8 source (`6776c28`) and its cutover report (`1b4ded5`); merged into main at this cleanup |
| [`ops/gen7-fast-selfplay-cloud-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/ops/gen7-fast-selfplay-cloud-20261111) | 11-11 23:28 | Cloud self-play collector runtime; conflicts with main (backlog 1) |
| [`ops/gen71-19bbdce5-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/ops/gen71-19bbdce5-20261112) | 11-12 06:28 | 19bbdce5 collector, Gen 7.1 preparation (`7d96087`); conflicts with main in `ops/prepare_gen7_alpha.py` (backlog 1) |
| [`ops/gen8-19bbdce5-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/ops/gen8-19bbdce5-20261112) | 11-12 16:42 | 19bbdce5 collector, deployed Gen 8 source (`c8a138f`): its plan and `--restore-actors`; merged into main at this cleanup |

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

## Gen 8 feeds (13)

Producer publications for the current generation. Never merge. Board counts are from about 18:10 UTC and grow.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`arena-gen8-19bbdce5-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-19bbdce5-20261112-feed) | 11-12 18:15 | Gen 8 · stream19bbdce5 main mix; 143 boards; read at its head |
| [`arena-gen8-azure1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure1-feed) | 11-12 18:15 | Gen 8 · azure1 (main mix); 433 boards; read at its head |
| [`arena-gen8-azure3-ben64-1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-1-feed) | 11-12 18:15 | Gen 8 · azure3 (BEN 64, lane 1); 54 boards; read at its head |
| [`arena-gen8-azure3-ben64-2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-2-feed) | 11-12 18:15 | Gen 8 · azure3 (BEN 64, lane 2); 55 boards; read at its head |
| [`arena-gen8-azure3-ben64-3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-3-feed) | 11-12 18:15 | Gen 8 · azure3 (BEN 64, lane 3); 57 boards; read at its head |
| [`arena-gen8-azure3-ben64-4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-4-feed) | 11-12 18:15 | Gen 8 · azure3 (BEN 64, lane 4); 54 boards; read at its head |
| [`arena-gen8-azure3-ben64-5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-5-feed) | 11-12 18:15 | Gen 8 · azure3 (BEN 64, lane 5); 60 boards; read at its head |
| [`arena-gen8-azure3-ben64-6-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-6-feed) | 11-12 18:15 | Gen 8 · azure3 (BEN 64, lane 6); 57 boards; read at its head |
| [`arena-gen8-azure3-ben64-7-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-7-feed) | 11-12 18:15 | Gen 8 · azure3 (BEN 64, lane 7); 58 boards; read at its head |
| [`arena-gen8-azure3-ben64-8-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure3-ben64-8-feed) | 11-12 18:16 | Gen 8 · azure3 (BEN 64, lane 8); 56 boards; read at its head |
| [`arena-gen8-azure6-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-azure6-feed) | 11-12 18:11 | Gen 8 · azure6 (main mix); 408 boards; read at its head |
| [`arena-gen8-candidate-codex-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-candidate-codex-20261112-feed) | 11-12 18:15 | Gen8 · Codex main mix (standard and Precision); 131 boards; read at its head |
| [`arena-gen8-independent-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen8-independent-feed) | 11-12 18:15 | Gen8 independent · standard, Precision and BEN anchors; 48 boards; read at its head |

## Gen 7 feeds (70)

Gen 7.0 and 7.1 publications, closed. Never merge. A feed not in the registry is not in Gen 7's table.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`arena-gen7-1-azure3-ben64-1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-1-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 29 boards |
| [`arena-gen7-1-azure3-ben64-2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-2-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 24 boards |
| [`arena-gen7-1-azure3-ben64-3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-3-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 27 boards |
| [`arena-gen7-1-azure3-ben64-4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-4-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 31 boards |
| [`arena-gen7-1-azure3-ben64-5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-5-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 30 boards |
| [`arena-gen7-1-azure3-ben64-6-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-6-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 29 boards |
| [`arena-gen7-1-azure3-ben64-7-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-7-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 29 boards |
| [`arena-gen7-1-azure3-ben64-8-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-azure3-ben64-8-feed) | 11-12 06:37 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 26 boards |
| [`arena-gen7-1-compare-azure2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-compare-azure2-feed) | 11-12 06:02 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 8 boards |
| [`arena-gen7-1-compare-codex-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-compare-codex-20261112-feed) | 11-12 16:30 | Gen 7.1 · Codex policy comparison and Gen6; 1,974 boards; retired |
| [`arena-gen7-1-fresh-azure3-ben64-1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-1-feed) | 11-12 13:03 | Gen 7.1 · azure3 (BEN 64, lane 1); 366 boards; read at its head |
| [`arena-gen7-1-fresh-azure3-ben64-2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-2-feed) | 11-12 12:56 | Gen 7.1 · azure3 (BEN 64, lane 2); 366 boards; read at its head |
| [`arena-gen7-1-fresh-azure3-ben64-3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-3-feed) | 11-12 12:41 | Gen 7.1 · azure3 (BEN 64, lane 3); 372 boards; read at its head |
| [`arena-gen7-1-fresh-azure3-ben64-4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-4-feed) | 11-12 12:43 | Gen 7.1 · azure3 (BEN 64, lane 4); 361 boards; read at its head |
| [`arena-gen7-1-fresh-azure3-ben64-5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-5-feed) | 11-12 13:16 | Gen 7.1 · azure3 (BEN 64, lane 5); 365 boards; read at its head |
| [`arena-gen7-1-fresh-azure3-ben64-6-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-6-feed) | 11-12 13:25 | Gen 7.1 · azure3 (BEN 64, lane 6); 369 boards; read at its head |
| [`arena-gen7-1-fresh-azure3-ben64-7-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-7-feed) | 11-12 13:09 | Gen 7.1 · azure3 (BEN 64, lane 7); 369 boards; read at its head |
| [`arena-gen7-1-fresh-azure3-ben64-8-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh-azure3-ben64-8-feed) | 11-12 13:28 | Gen 7.1 · azure3 (BEN 64, lane 8); 365 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-1-feed) | 11-12 16:14 | Gen 7.1 · azure3 (BEN 64, lane 1, pool 2); 185 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-2-feed) | 11-12 16:10 | Gen 7.1 · azure3 (BEN 64, lane 2, pool 2); 185 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-3-feed) | 11-12 15:41 | Gen 7.1 · azure3 (BEN 64, lane 3, pool 2); 185 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-4-feed) | 11-12 15:49 | Gen 7.1 · azure3 (BEN 64, lane 4, pool 2); 184 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-5-feed) | 11-12 16:15 | Gen 7.1 · azure3 (BEN 64, lane 5, pool 2); 184 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-6-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-6-feed) | 11-12 16:25 | Gen 7.1 · azure3 (BEN 64, lane 6, pool 2); 172 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-7-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-7-feed) | 11-12 16:22 | Gen 7.1 · azure3 (BEN 64, lane 7, pool 2); 184 boards; read at its head |
| [`arena-gen7-1-fresh2-azure3-ben64-8-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh2-azure3-ben64-8-feed) | 11-12 16:25 | Gen 7.1 · azure3 (BEN 64, lane 8, pool 2); 167 boards; read at its head |
| [`arena-gen7-1-fresh3-azure3-ben64-1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh3-azure3-ben64-1-feed) | 11-12 16:25 | Not in the registry (backlog 12): Gen 7.1, drained at the switch to Gen 8; 9 boards |
| [`arena-gen7-1-fresh3-azure3-ben64-2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh3-azure3-ben64-2-feed) | 11-12 16:25 | Not in the registry (backlog 12): Gen 7.1, drained at the switch to Gen 8; 11 boards |
| [`arena-gen7-1-fresh3-azure3-ben64-3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh3-azure3-ben64-3-feed) | 11-12 16:25 | Not in the registry (backlog 12): Gen 7.1, drained at the switch to Gen 8; 40 boards |
| [`arena-gen7-1-fresh3-azure3-ben64-4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh3-azure3-ben64-4-feed) | 11-12 16:25 | Not in the registry (backlog 12): Gen 7.1, drained at the switch to Gen 8; 37 boards |
| [`arena-gen7-1-fresh3-azure3-ben64-5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh3-azure3-ben64-5-feed) | 11-12 16:25 | Not in the registry (backlog 12): Gen 7.1, drained at the switch to Gen 8; 7 boards |
| [`arena-gen7-1-fresh3-azure3-ben64-7-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-fresh3-azure3-ben64-7-feed) | 11-12 16:25 | Not in the registry (backlog 12): Gen 7.1, drained at the switch to Gen 8; 1 boards |
| [`arena-gen7-1-mix-azure1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-mix-azure1-feed) | 11-12 14:02 | Gen 7.1 · azure1 (self-play and against Gen 7.0); 1,256 boards; read at its head |
| [`arena-gen7-1-mix2-azure1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-mix2-azure1-feed) | 11-12 16:21 | Not in the registry (backlog 12): Gen 7.1, drained at the switch to Gen 8; 381 boards |
| [`arena-gen7-1-vs70-azure2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-vs70-azure2-feed) | 11-12 06:33 | Not in the registry, by design: closed on 12 November at 06:32 to 06:39 UTC because policy net v4.1 was trained on its deals; 160 boards |
| [`arena-gen7-1-vs70-fresh-azure2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-1-vs70-fresh-azure2-feed) | 11-12 08:13 | Gen 7.1 · azure2 against Gen 7.0, every board; 745 boards; read at its head |
| [`arena-gen7-independent-selfplay-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-independent-selfplay-feed) | 11-12 06:03 | Gen7 independent · completed v4 self-play and anchors; 420 boards; retired |
| [`arena-gen7-phase1-azure1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure1-feed) | 11-12 11:41 | Gen 7 · azure1 phase 1 (non-BEN); 828 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-1-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 1); 148 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-2-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 2); 149 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-3-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 3); 159 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-4-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 4); 154 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-5-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 5); 153 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-6-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-6-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 6); 139 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-7-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-7-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 7); 151 boards; read at its head |
| [`arena-gen7-phase1-azure2-ben16-8-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-ben16-8-feed) | 11-12 06:01 | Gen 7 · azure2 phase 1 (BEN 16, lane 8); 142 boards; read at its head |
| [`arena-gen7-phase1-azure2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure2-feed) | 11-12 03:48 | Gen 7 · azure2 phase 1 (non-BEN); 608 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-1-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 1); 79 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-2-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 2); 75 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-3-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 3); 74 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-4-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 4); 83 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-5-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 5); 79 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-6-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-6-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 6); 71 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-7-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-7-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 7); 71 boards; read at its head |
| [`arena-gen7-phase1-azure3-ben64-8-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-ben64-8-feed) | 11-12 06:02 | Gen 7 · azure3 phase 1 (BEN 64, lane 8); 74 boards; read at its head |
| [`arena-gen7-phase1-azure3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure3-feed) | 11-12 03:51 | Gen 7 · azure3 phase 1 (non-BEN); 720 boards; read at its head |
| [`arena-gen7-phase1-azure4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-azure4-feed) | 11-12 18:15 | Gen 7 · azure4 phase 1 (non-BEN); 829 boards; read at its head |
| [`arena-gen7-phase1-cloud-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-cloud-feed) | 11-12 04:25 | Gen 7 · cloud phase 1 (non-BEN); 67 boards; retired |
| [`arena-gen7-phase1-codex-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-codex-20261112-feed) | 11-12 04:28 | Gen 7 · Codex completed phase 1 anchors; 564 boards; retired |
| [`arena-gen7-phase1-extra-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-extra-feed) | 11-12 04:30 | Gen7 additional phase1 non-BEN; 37 boards; retired |
| [`arena-gen7-phase1-independent-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-independent-feed) | 11-12 04:49 | Gen7 independent · completed five-pair phase1 cohort; 387 boards; retired |
| [`arena-gen7-phase1-selfplay-azure2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-phase1-selfplay-azure2-feed) | 11-12 06:08 | Gen 7 · azure2 standard self-play and Gen 6 comparison; 11 boards; read at its head |
| [`arena-gen7-pre7-azure1-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-pre7-azure1-feed) | 11-12 03:09 | Gen 7 · azure1 pre-arena test (vs Gen 6 fast); 538 boards; retired |
| [`arena-gen7-pre7-azure2-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-pre7-azure2-feed) | 11-12 03:09 | Gen 7 · azure2 pre-arena test (vs Gen 6 fast); 363 boards; retired |
| [`arena-gen7-pre7-azure3-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-pre7-azure3-feed) | 11-12 03:09 | Gen 7 · azure3 pre-arena test (vs Gen 6 fast); 374 boards; retired |
| [`arena-gen7-pre7-azure4-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-pre7-azure4-feed) | 11-12 03:09 | Gen 7 · azure4 pre-arena test (vs Gen 6 fast); 362 boards; retired |
| [`arena-gen7-selfplay-capture-codex-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-selfplay-capture-codex-20261112-feed) | 11-12 06:29 | Gen 7.0 · Codex completed self-play with gap capture; 437 boards; retired |
| [`arena-gen7-selfplay-codex-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen7-selfplay-codex-20261112-feed) | 11-12 04:36 | Gen 7 · Codex initial self-play (capture incomplete); 32 boards; retired |
| [`arena-gen71-19bbdce5-20261112-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen71-19bbdce5-20261112-feed) | 11-12 16:30 | Gen 7.1 · completed comparisons stream19bbdce5; 2,189 boards; retired |
| [`arena-gen71-independent-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen71-independent-feed) | 11-12 17:45 | Gen7.1 independent · completed policy comparison and anchors; 3,293 boards; retired |

## Gen 6 feeds and controller records (17)

Gen 6 publications and controller logs, closed. Never merge.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`arena-gen6-ben-expansion-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-ben-expansion-feed) | 11-11 05:46 | Gen5: 248 verified paired deals, common/native bidding |
| [`arena-gen6-chatgpt-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-chatgpt-feed) | 11-12 17:54 | Gen6 ChatGPT: verified independent cohort snapshot and complete recovery records |
| [`arena-gen6-codex-ben-followups-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-ben-followups-feed) | 11-11 05:52 | Gen5: 217 verified paired deals, common/native bidding |
| [`arena-gen6-codex-ben-gate`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-ben-gate) | 11-11 05:21 | Record arena controller observations and recovery status |
| [`arena-gen6-codex-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-feed) | 11-11 05:16 | Gen5: 1543 verified paired deals, common/native bidding |
| [`arena-gen6-codex-v7-capture-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-v7-capture-feed) | 11-11 09:16 | Gen5: 1134 verified paired deals, common/native bidding |
| [`arena-gen6-codex-v7-cutover`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-v7-cutover) | 11-11 05:56 | Record arena controller observations and recovery status |
| [`arena-gen6-codex-v7-watch`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-codex-v7-watch) | 11-11 11:58 | Record arena controller observations and recovery status |
| [`arena-gen6-extra-selfplay-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-extra-selfplay-feed) | 11-12 03:34 | Additional Gen6 fast self-play: arena and complete Gen7 training recovery snapshot |
| [`arena-gen6-fast-selfplay-20261111-19bbdce5-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-20261111-19bbdce5-feed) | 11-12 06:32 | Gen5: 4722 verified paired deals, common/native bidding |
| [`arena-gen6-fast-selfplay-cloud-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-cloud-feed) | 11-12 02:24 | Gen7 cloud self-play: 1672 boards and full recovery snapshot |
| [`arena-gen6-fast-selfplay-codex-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-codex-20261111) | 11-12 02:43 | Gen6 fast self-play: 3710 verified deals |
| [`arena-gen6-fast-selfplay-independent-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/arena-gen6-fast-selfplay-independent-feed) | 11-12 03:29 | Gen5: 9694 verified paired deals, common/native bidding |
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

## Control channels (16)

Box control, coordination and team channels. Never merge.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`box/azure1/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure1/control) | 11-12 17:56 | boxctl command queue for azure1 |
| [`box/azure1/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure1/status) | 11-12 18:13 | boxctl heartbeat and results of azure1 |
| [`box/azure2/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure2/control) | 11-12 17:09 | boxctl command queue for azure2 |
| [`box/azure2/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure2/status) | 11-12 18:16 | boxctl heartbeat and results of azure2 |
| [`box/azure3/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure3/control) | 11-12 17:50 | boxctl command queue for azure3 |
| [`box/azure3/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure3/status) | 11-12 18:11 | boxctl heartbeat and results of azure3 |
| [`box/azure4/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure4/control) | 11-12 18:04 | boxctl command queue for azure4 |
| [`box/azure4/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure4/status) | 11-12 18:15 | boxctl heartbeat and results of azure4 |
| [`box/azure5/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure5/control) | 11-12 17:09 | boxctl command queue for azure5 |
| [`box/azure5/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure5/status) | 11-12 18:11 | boxctl heartbeat and results of azure5 |
| [`box/azure6/control`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure6/control) | 11-12 18:12 | boxctl command queue for azure6 |
| [`box/azure6/status`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/azure6/status) | 11-12 18:12 | boxctl heartbeat and results of azure6 |
| [`box/coordination`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/box/coordination) | 11-12 18:13 | Coordination board of the sessions and the Azure allocation table; append-only |
| [`fleet/azure`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/fleet/azure) | 11-12 16:48 | The operator's Azure fleet status (`STATUS.md`) |
| [`team/gen9`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/team/gen9) | 11-12 18:15 | The Gen 9 team's channel |
| [`work/ledger`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/work/ledger) | 11-12 07:03 | Work ledger; retired 12 November 06:58 UTC in favour of `team/gen9` |

## Transfers (39)

Dataset, model and result handoffs with restore instructions.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`transfer/ben-lanes-azure-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/ben-lanes-azure-20261112) | 11-12 07:55 | BEN lanes on Azure: install command, lane tools and memory supervisor, for Gen 9 (copies) |
| [`transfer/dds-bidding-40000-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/dds-bidding-40000-20261110) | 11-10 20:38 | Publish exact 40K bidding DDS training deals and 1K development set |
| [`transfer/gen3-resume-3701`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen3-resume-3701) | 11-09 08:00 | Test watchdog recovery through verified independent launcher |
| [`transfer/gen3-training-feed`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen3-training-feed) | 11-09 22:55 | Training snapshot-0019: upload 6/6 |
| [`transfer/gen6-candidate-bidder-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen6-candidate-bidder-20261111) | 11-11 00:33 | Add Gen 6 candidate bidder release (graded alternatives) |
| [`transfer/gen6-launch-package-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen6-launch-package-20261111) | 11-11 02:05 | Gen 6 doc: final layout-selection numbers; add the test's records |
| [`transfer/gen7-capture-forks-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-capture-forks-20261111) | 11-11 05:35 | Gap forks and guess-size logging, as applied on collectors |
| [`transfer/gen7-policy-v4.1-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-policy-v4.1-20261112) | 11-12 08:03 | Policy net v4.1: the release folder that is on main, with scoring and near-tie logs |
| [`transfer/gen7-policy-v4.1-bench-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-policy-v4.1-bench-20261112) | 11-12 05:09 | Policy 4.1: tree bench rows on fresh fork pairs (v4's tree and 4.1's tree on the same pairs) |
| [`transfer/gen7-policy-v4.1-box-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-policy-v4.1-box-20261112) | 11-12 07:34 | Policy 4.1 training box output (azure5): nets by epoch, logs, manifests, fork pairs, bench rows, checks |
| [`transfer/gen7-policy-v4.1-families-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-policy-v4.1-families-20261112) | 11-12 14:02 | The 34,029 deal families in policy net v4.1's training file |
| [`transfer/gen7-policy-v4.1-lists-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-policy-v4.1-lists-20261112) | 11-12 05:51 | Policy 4.1: blob ids of the fresh episodes on deals the training set does not have (sets B, C, D), in two shards |
| [`transfer/gen7-policy-v4.1-neartie-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-policy-v4.1-neartie-20261112) | 11-12 07:12 | Near-tie selectors on fresh fork pairs: reports and logs |
| [`transfer/gen7-prototype-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-prototype-20261111) | 11-12 02:24 | Gen 7 build session save points |
| [`transfer/gen7-selfplay-trial-azure2-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen7-selfplay-trial-azure2-20261112) | 11-12 04:40 | Gen5: 4 verified paired deals, common/native bidding |
| [`transfer/gen71-settings-azure1-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen71-settings-azure1-20261112) | 11-12 15:47 | Gen 7.1 settings matches on azure1 (`FINDINGS.md`), stopped at Max's word at 15:46 UTC |
| [`transfer/gen8-p41-reading-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen8-p41-reading-20261112) | 11-12 13:00 | Gen 8 reading bench: reports |
| [`transfer/gen8-p41-reading-pools-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen8-p41-reading-pools-20261112) | 11-12 12:29 | Gen 8 reading bench: stored pools |
| [`transfer/gen8-proto-azure1-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen8-proto-azure1-20261112) | 11-12 12:29 | Gen 8 prototype match results from azure1 |
| [`transfer/gen8-proto-azure3-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen8-proto-azure3-20261112) | 11-12 03:17 | Gen 8 prototype match results from azure3 |
| [`transfer/gen8-proto-azure4-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen8-proto-azure4-20261112) | 11-12 14:58 | Gen 8 prototype match results from azure4 |
| [`transfer/gen8-proto-azure6-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen8-proto-azure6-20261112) | 11-12 16:03 | Gen 8 prototype match results from azure6 |
| [`transfer/gen9-arrival-rehearsal-2-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen9-arrival-rehearsal-2-20261112) | 11-12 13:21 | Release check rerun on 8cb0348 (card_on_nets off): met for both guests |
| [`transfer/gen9-arrival-rehearsal-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen9-arrival-rehearsal-20261112) | 11-12 09:09 | Arrival-run rehearsal records (G9-D6): three epochs of 24 boards, guest-a arriving before epoch 2 |
| [`transfer/gen9-arrival-rehearsal-full-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen9-arrival-rehearsal-full-20261112) | 11-12 10:29 | Arrival-run full-path rehearsal records (G9-D6): the box run's events on five 16-board epochs, fresh worktree |
| [`transfer/gen9-d6-arrival-azure4-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen9-d6-arrival-azure4-20261112) | 11-12 17:53 | azure4: d6-arrival results, 2315 boards |
| [`transfer/gen9-e9-0-n02-azure4-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen9-e9-0-n02-azure4-20261112) | 11-12 18:14 | azure4: e9-0-n02 results, 208 boards |
| [`transfer/gen9-e9-0-n02e-azure4-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen9-e9-0-n02e-azure4-20261112) | 11-12 18:14 | azure4: e9-0-n02e results, 208 boards |
| [`transfer/gen9-e9-16-pilot-sandbox-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/gen9-e9-16-pilot-sandbox-20261112) | 11-12 17:23 | E9-16 sandbox pilot (not part of the result): 8r-32~8p-32, 400 boards, seed 917, source 491c7f7 |
| [`transfer/graded-alternatives-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/graded-alternatives-20261110) | 11-10 22:10 | Add graded-alternatives bidder experiment (candidate Gen 6 bidder) |
| [`transfer/non-v4-policy-play-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/non-v4-policy-play-20261109) | 11-09 23:43 | Add verified pre-Gen4 model training tensors and 9000 raw PIMC games |
| [`transfer/plan-leverage-azure2-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/plan-leverage-azure2-20261112) | 11-12 18:15 | Plan-leverage research outputs from azure2, 2026-11-12T18:15:22Z |
| [`transfer/plan-leverage-azure5-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/plan-leverage-azure5-20261112) | 11-12 18:14 | Plan-leverage research outputs from azure5, 2026-11-12T18:14:38Z |
| [`transfer/pre7-test-azure1-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure1-20261112) | 11-12 03:12 | pre7-test: g7s-vs-g6f-01, 538 episodes |
| [`transfer/pre7-test-azure2-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure2-20261112) | 11-12 03:12 | pre7-test: pre7-7s-vs-6f-azure2, 363 episodes |
| [`transfer/pre7-test-azure3-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure3-20261112) | 11-12 03:12 | pre7-test: pre7-7s-vs-6f-azure3, 374 episodes |
| [`transfer/pre7-test-azure4-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/pre7-test-azure4-20261112) | 11-12 03:12 | pre7-test: pre7-7s-vs-6f-azure4, 362 episodes |
| [`transfer/v4-worker-standby`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/v4-worker-standby) | 11-09 13:25 | Add safe second-chat standby instructions |
| [`transfer/v41-training-families-union-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/transfer/v41-training-families-union-20261112) | 11-12 16:13 | The 34,092 deal families of policy net v4.1's training set (union of the two published lists): the exclusion list of every Gen 8 cohort |

## Archives (1)

Preserved excluded observations.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`archive/gen6-fast-ben-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/archive/gen6-fast-ben-20261111) | 11-11 02:42 | 13 accidental fast-vs-BEN16 games, excluded from scores |

## Gen 9 development (22)

Work in progress for the next generation; not on main, not in the arena. Notes are last commit subjects.

| Branch | Last commit | Note |
| --- | --- | --- |
| [`feature/gen9`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9) | 11-12 17:54 | Leakage report: part 1c (equal-best sets: 0.009 +- 0.017 tricks) and the first played figure (+0.17 +- 0.17 IMPs over 400 boards) |
| [`feature/gen9-arena-arrival`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-arena-arrival) | 11-12 18:14 | Rule bidder: no response table for an opening its tables never make (another system's 3NT); arena runner records a board that raises |
| [`feature/gen9-arena-design`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-arena-design) | 11-12 06:56 | Gen 9 arena note: training-only boards for bundles that saw the family; refuse oracle bots at admission |
| [`feature/gen9-arena-epochs`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-arena-epochs) | 11-12 07:46 | Merge remote-tracking branch 'origin/feature/gen9' into feature/gen9-arena-epochs |
| [`feature/gen9-arena-experience`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-arena-experience) | 11-12 07:19 | Gen 9 experience store (G9-D5): envelopes from collectors, an order-free merge, epoch snapshots |
| [`feature/gen9-arena-ratings`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-arena-ratings) | 11-12 07:29 | Gen 9 ratings-v1 from every published paired result, Gen 5 to 7.1 (G9-D3) |
| [`feature/gen9-arena-sim`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-arena-sim) | 11-12 07:22 | Gen 9 arena statistics in code (G9-A4) and E9-5 on them: betting test, rating coverage, gain rule |
| [`feature/gen9-bidding-cards`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-bidding-cards) | 11-12 10:01 | docs/gen9/bidding.md: status at 12 Nov 10:00 UTC, with what each step is worth where measured |
| [`feature/gen9-bidding-design`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-bidding-design) | 11-12 07:04 | Gen 9: bidding design note (G9-B1): card IR, compile, the rule filter, profiles |
| [`feature/gen9-e9-17`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-e9-17) | 11-12 17:18 | E9-17: r9t-32, the signal reader told t-high's, t-low's and t-random's fixed carding rule |
| [`feature/gen9-reading-bench`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-reading-bench) | 11-12 18:15 | G9-X2: will's review notes (reading (2) is in the sandbox; the bench tests' data named in the test file) |
| [`feature/gen9-signals`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-signals) | 11-12 07:38 | House carding report: the experiment file is E9-9 |
| [`feature/gen9-signals-design`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-signals-design) | 11-12 07:19 | Signals note: suit-preference and Lavinthal suit pairs; undeclared fields stay Gen 8's; direction-only descriptors are inert |
| [`feature/gen9-signals-v2`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-signals-v2) | 11-12 17:52 | docs/gen9/signals-results.md: today's results in tricks (bench), E9-14, E9-15, E9-16 parts 1b and 1c |
| [`feature/gen9-workflow-ben-lanes`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-workflow-ben-lanes) | 11-12 12:32 | gen9_ben_lanes: a tag in every unit and namespace name (default the --out folder), so two queue jobs on one box never share a lane; --ben-bot ben64 (p |
| [`feature/gen9-workflow-design`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-workflow-design) | 11-12 07:10 | Gen 9 workflow design note (G9-W1): work queue and experiment registry |
| [`feature/gen9-workflow-tests`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-workflow-tests) | 11-12 07:33 | run_tests.py: run pytest-style test files under pytest |
| [`feature/gen9-workflow-tests-2`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-workflow-tests-2) | 11-12 07:48 | run_tests.py: --prepare skips every release that is already restored, whatever its manifest's shape |
| [`feature/gen9-workflow-tests-3`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-workflow-tests-3) | 11-12 08:25 | run_tests.py: a test file with no tests found fails the run |
| [`feature/gen9-workflow-tests-4`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/gen9-workflow-tests-4) | 11-12 18:14 | run_tests.py: the per-file line counts skipped tests, and --files with a file that does not exist stops with its name instead of a traceback |
| [`feature/work-ledger-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/feature/work-ledger-20261112) | 11-12 07:02 | Work ledger v2, the Gen 9 team's file format and protocol; not on main |
| [`research/gen9-spot-equivalence`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/gen9-spot-equivalence) | 11-12 07:06 | Gen 9 experiment E9-3: spot cards and double-dummy equivalence |

## Research and experiments (46)

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
| [`research/hand-fit-scorer-v1a-20261111`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/hand-fit-scorer-v1a-20261111) | 11-11 21:38 | Hand-fit scorer v1a, packaged; not adopted (backlog 7) |
| [`research/imp-policy-draft`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/imp-policy-draft) | 11-09 01:41 | Add direct auction policy bootstrap and random recursive IMP audits |
| [`research/joint-auction-belief-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/joint-auction-belief-20261110) | 11-11 02:06 | Add layout-selection test results to the play report (research prototype) |
| [`research/large-belief-play-test`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/large-belief-play-test) | 11-09 00:17 | Promote larger belief net on validation predictions; add cached mixed play |
| [`research/layout-embedding-20261110`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/layout-embedding-20261110) | 11-10 07:50 | Complete independent 200-deal large-position sampling evaluation |
| [`research/mixed-fork-generations`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/mixed-fork-generations) | 11-09 03:56 | Add conditional 10k decision point before successor training |
| [`research/multiscore-16-32-64`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/multiscore-16-32-64) | 11-09 05:31 | PR #9 (backlog 10) |
| [`research/outcome-policy-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/outcome-policy-20261109) | 11-09 21:26 | Publish outcome-trained scalar and distribution models with held-out results |
| [`research/pimc-study-2026-11-08`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/pimc-study-2026-11-08) | 11-08 13:46 | Archive PIMC and alpha-mu experiments with larger cost study |
| [`research/plan-leverage-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/plan-leverage-20261112) | 11-12 18:11 | Leverage through plan-level search: reports and scripts; not on main |
| [`research/plan-leverage-g8-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/plan-leverage-g8-20261112) | 11-12 18:11 | The same research on top of the Gen 8 prototype (plan bots); not on main |
| [`research/policy-branch-ranking-20261109`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/policy-branch-ranking-20261109) | 11-09 19:30 | Evaluate Gen4 branch choices and train family-held-out IMP-weighted ranking policy |
| [`research/primary-component-diagnosis`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/primary-component-diagnosis) | 11-09 19:16 | Stop primary v4 self-play and freeze component diagnostic allocation |
| [`research/reauction-existing-10000`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/reauction-existing-10000) | 11-08 17:16 | Retrofit BEN auctions to 10000 deals and report matched-subset belief experiment |
| [`research/self-improvement-loop`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/self-improvement-loop) | 11-08 22:32 | Verify process handoff preserves saved collection records |
| [`research/selfplay-training-2026-11-08`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/selfplay-training-2026-11-08) | 11-08 22:00 | Report completed 1000-deal policy increment over belief-informed PIMC |
| [`research/shared-beliefs-dds-cache`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/shared-beliefs-dds-cache) | 11-08 23:54 | PR #4 (backlog 9) |
| [`research/sure-trick-table-20261112`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/sure-trick-table-20261112) | 11-12 18:08 | Sure-trick search, strategy-fusion test deals and ending-table build spec |
| [`research/three-engine-play-200`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/three-engine-play-200) | 11-08 18:06 | Compare baseline, bidding-informed PIMC and BEN on the same 200 deals |
| [`research/v4-belief-and-arena`](https://github.com/maxschireson/Single-Dummy-Bridge/tree/research/v4-belief-and-arena) | 11-09 11:00 | Train additive v4 belief and preserve resumable model and paired uncertainty results |

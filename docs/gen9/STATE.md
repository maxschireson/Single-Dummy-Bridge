# Gen 9: state at the freeze, Fri 13 Nov 18:00 UTC (hand-over note)

> **13 Nov 01:18 UTC: Gen 9 continues in parallel with 8X** (Max, 01:13 and 01:16). 8X is a separate release with
> more limited goals, a higher-leverage prototype the plan session pushes out quickly; it has first call on anything
> it needs from us. Gen 9's centre is now managing a highly diverse arena as the environment for self-play training.
> azure4 stays with Gen 9's queue. Gen 9's pieces are offered to 8X (board, 00:14), optional. 8X randomizes among
> exactly equal cards if the two leakage matches show no played cost (Max agreed, 00:28).

Written by g9 for whoever picks this up (a later g9 session, a helper, or Max). Everything here is on `feature/gen9`
or `team/gen9` unless a branch is named. Experiment files are `team/gen9:experiments/E9-*.md`; tasks are
`team/gen9:tasks/*.md`; `tools/workq.py` (on `team/gen9`) reads both.

## Dates

- Fri 13 Nov 18:00 UTC: freeze (no new runs started after it). Passed; the numbers below are the freeze's: the last
  feed commits before 18:00 (cohort 17:59:47, BEN pair 17:59:24) and `team/gen9` at 18:01.
- Sat 14 Nov 01:00 UTC (Friday evening California): review package for Max (task G9-A6, g9). The page is final
  at the freeze numbers (a Claude doc, private to Max, rev 31): https://claude.ai/artifact/Mc5Fhz74bcoUJND3bHMUzL.

## Running

- **azure4** (Gen 9's only box; no instance added): will's job queue (`tools/boxq.py`); `tools/q jobs` shows it. Idle 2.8
  core-hours since 12 Nov 15:03 of about 216, all while jobs waited (STATUS, 18:01).
  - `g9-cohort-azure4` (dave, priority 1, since 06:44 UTC; 6 cores and 5 workers since 10:14): the Gen 9 cohort, `configs/round9-cohort.json`
    on `feature/gen9-cohort` (46b7e004): `9a-32` against `8s-32`, `71s-32` and `8p-32` (the control) on 10,000 fresh
    deals (seed 9013), cohort identity 75b73937750652a5. At the freeze 1,783 of 10,000; `9a-32`'s IMPs a board against
    `71s-32` +0.54 +- 0.15 (594 boards), `8p-32` +0.30 +- 0.15 (594), `8s-32` +0.17 +- 0.13 (595). Both tables bid the same
    auction on all 1,783 boards (`different_bidding` false in the replays), so these compare card play. 160 to 167
    boards an hour until about 16:45, about 105 since (below), so about 2,500 by the review and all 10,000 near 17 Nov 01:00. Feed `arena-gen9-azure4-feed`, registered on the page by g7 as generation 9
    (`gen9azure4`); the page's default view is Gen 9 since 07:19 UTC (Max). `9a-32` takes 0.354 s per card
    decision with a choice against `8p-32`'s 0.376 on the same box.
  - `9a-32~ben64`: job `g9-cohort-ben64-azure4` since about 07:50 UTC, 2,000 fresh deals (seed 9014), feed
    `arena-gen9-azure4-ben64-feed`, BEN 64 through will's `gen9_ben_lanes serve`. At the freeze 454 of 2,000, +0.19 +- 0.18 IMPs a board; about
    46 an hour, ending about 15 Nov 03:30 by the queue's estimate, which frees the core E9-25 waits for.
  - Paused until the cohort ends: `e9-0-n04` (284 of 800), `e9-16-h-v-p` (269 of 800), both g9's. Waiting: `e9-25`.
  - **Disk (will, 17:52):** azure4's P10 disk (Premium_LRS, 128 GB) is at its write limit, 595 writes/s at 42 ms, which
    looks like the 500-IOPS baseline after the burst credits ran out; CPU 45% idle. Most writes are the cohort's
    `run/dds-cache.sqlite` (11.4 GB, 6.5 MB a board, WAL with `synchronous=FULL`, `bridge_harness/dds_cache.py`). will's
    options: (1) `synchronous=NORMAL` or the cache off, a source change mid-run; (2) a fresh cache; (3) a faster disk,
    which costs money (Max's rule: recap, then his go); (4) leave it. g9 (18:10, to all): leave it tonight; first a fresh
    cache on a local temp disk if azure4 has one (a symlink; check that SQLite puts `-wal` and `-shm` beside the real
    file); else (1), logged with its commit: play is unchanged, but the manifest's `source_sha256` covers every
    `bridge_harness/*.py`. dave decides as owner; if he is silent at 08:00 UTC on 14 Nov, will may apply it on g9's
    agreement; (3) only through a recap to Max. At 6.5 MB a board the cache reaches about 65 GB by 10,000 boards; will to
    check free space (STATUS's 108.5 GB is from 12 Nov 17:49). A Gen 7 publisher (pid 5704) still writes about 0.4 MB/s
    on azure4; will raised it with g7 and is not touching it.
- **The ladder** (G9-D9, dave and will, accepted 07:24): `arena/ladder.json` and `ladder.js` at the top of the arena page,
  refreshed hourly; the cohort's points appear as its boards come in.

## 13 November (with where they are)

- **Arena design note for the review**: `docs/gen9/arena-selfplay.md` (G9-A8, dave reviewing). Roles in the
  population, three diversity distances and a redundancy rule, training opponents by what the champion still has to
  learn, ratings in a diverse field, exploiters and leakage, the nets' view of a newcomer, page additions, five decisions
  for Max, tasks E9-18 to E9-23, G9-B9, G9-S8, G9-D10.
- **E9-21** (adopted by will, 08:27): on the ladder's 22 points the field moves the levels, not the order;
  the equilibrium is `8s-32` alone; the Nash average's errors are about the field scores'. `reports/gen9-arena-field-2026-11-13`.
- **E9-20** (rejected as worded by will, 08:27): no current member is redundant. By results alone `6-32` and `8c-32` look alike; by card
  play alone `8c-32` and `8s-32` never chose differently in 25,953 paired decisions (they differ only in bidding, 0.79
  IMPs a board natively). `reports/gen9-arena-diversity-2026-11-13`.
- **E9-19** (the cheap version was rejected by will, 13:35; below): on 64,790 native boards, boards where the two tables' contracts differ carry 30% of house pairs'
  variance (55% with BEN), so re-scoring contracts can cut the SD by at most 16% (33%); most of the variance is card
  play in the same contract.
- **E9-12 interim** (bill, 04:02): `9c-32` (reads the foreign system by its card) against `8p-32` +0.375 +- 0.092 IMPs a
  board over 902 boards; `9x-32` (rule replay) +0.410 +- 0.157 over 295; `9u-32` (reads no auction) -0.010 +- 0.126.

## Results of 12 November (with where they are)

Reading, in double-dummy tricks a board on p41's 530 house tables (`transfer/gen8-p41-reading-pools-20261112`), the
prototype `8p-32` as the base; about 3.6 to 4 IMPs a trick:
- The whole auction reading +0.107 +- 0.019; the whole play reading +0.185 +- 0.029; what is left to a player who
  sees every card 0.546, four fifths of it at tricks 1 to 6. `reports/gen9-auction-worth-2026-11-12`.
- **The bench predicts play.** E9-0 on the box, near-oracle help toward the true deal: +0.683 +- 0.119 IMPs a board
  (596 boards) against the proxy's +0.61; tricks 1 to 6 only +0.537 +- 0.121 against +0.51; the difference +0.148 +-
  0.053 against +0.10. So offline tricks are the currency for judging readers (task G9-X2, sam's bench stage,
  PR #30, reviewed by will).
- Bidding (bill): a system the scorer never saw is read 5.6 nats worse than not at all; the card 2.5 better; a
  replayed bidder 3.6 better (E9-1, E9-8). The card multiplied onto a matching profile hurts (now off by default,
  `card_on_nets`). A better reading of an auction we already read is worth a few hundredths of a trick.
- Signals (sam): house bots signal nothing (E9-9). A declared scheme told to the reader +0.062 +- 0.029 tricks a board
  over Gen 8 (honesty 0.8; about +0.22 IMPs), the largest reading gain of the day. The emission model of BEN +0.015 +-
  0.016; the per-situation expert for BEN (E9-15) adds nats and no tricks; the head fitted to BEN's declarer play
  (E9-14) +0.013 and +0.035 (BEN 16, 64). A signalling pair gains +0.06 tricks against `8p-32`, mostly by being
  misread, and nothing against a declarer told the scheme (E9-6 bench).
- Leakage (E9-16, g9; Max's question of 14:53): the opponents' reading of our plays is worth 0.124 +- 0.026 tricks a
  board to a reader of our strength; the defenders' plays are worth +0.029 to the defence and +0.101 to declarer.
  Randomizing among exactly equal cards is free double dummy and denies the reader 0.01 to 0.04 tricks; randomizing
  close choices costs about what it denies (0.020 within 0.02 tricks, 0.065 within 0.05). Sandbox pilot of `8r-32`
  (random among equal cards) against `8p-32`: +0.17 +- 0.17 IMPs over 400 boards. `reports/gen9-leakage-2026-11-12`.
- The convention-card reader against fixed carding rules (E9-17, dave): against t-high -0.10 +- 0.14, against t-low
  +0.09 +- 0.14 IMPs over the scaled net; prediction (+0.1) not met.
- Arrival run interim (epoch 2): against the foreign-system guest, `9a-32` reads the auction +4.30 +- 0.37 nats
  better than `8p-32` and scores +0.43 +- 0.26 IMPs a board better.

- **Margin and noise in ratings** (for the arena design note; Max asked 13 Nov 01:22 whether ratings should be Elo with
  margin as a factor). On E9-0's two 800-board box matches: boards of 10 or more IMPs (5% of boards) carry 61% to 65%
  of the IMPs won and about 80% of the variance; counting boards won and lost detects the same edge with 1.5 to 1.9
  times fewer boards (z 7.7 against 6.3; 6.7 against 4.8), and margins capped at 2 IMPs do the same. Ratings stay in
  IMPs a board (the objective); won/lost or capped margins are candidates for a faster screen; a double-dummy luck
  adjustment of the large swings is to be tested.

- **13 Nov 02:45 UTC.** Leakage, box (E9-16 part 2): `8r-32` (random among exactly equal cards) against `8p-32`
  +0.014 +- 0.126 IMPs a board (no played cost; condition for 8X's default met, posted for x8); against a reader at
  factor 0.25 +0.306 +- 0.125, so scaling a reader down against a randomizer costs it 0.29 +- 0.15 (read by class
  instead). Arrival run (G9-D6, accepted): `9a-32` minus `8p-32` against a guest with declared upside-down carding
  +0.479 +- 0.131, nearly all from reading its cards; guest-b's native cost -0.347 +- 0.160 unexplained (dave). E9-0
  adopted (bench predicts play). E9-17 inconclusive. E9-11 rejected on the bench (sam). The 8X engine belongs to the
  `x8` session (`feature/gen8x-rollout-bot-20261113`), not plan; Gen 9's offer was redirected to x8 (board, 02:45).

## Decided

- The player model, the mixture over profiles and the rule for mixing kinds of profile row: `docs/gen9/architecture.md`
  (revised 12 Nov). The shell: `bridge_harness/gen9.py`; arrival and belief: `bridge_harness/player_model.py`.
- Readers are judged in tricks on stored solves first; a match only when the bench says it can be seen.
- Rules for the team (12 Nov): any lead other than the owner may give an experiment verdict 60 minutes after
  submission (workq applies it since 22:15); will releases a blocked request on a written check after 30 minutes of
  g9's silence. Module reviews between leads (bill with sam, dave with will).

- **Max, 07:48 UTC:** no sub-agents (issue #23 closed); the promotion lead is g9's call: 0.10 IMPs a board, smaller
  gains through the bench and arena non-inferiority (issue #24 closed). SiD and the conditional claims into Gen 9: plan
  `docs/gen9/sid-integration.md` (G9-A9; tasks E9-24, G9-A10, G9-S9); question to x8 on the board about who builds
  conditional claims in the 8X engine.
- **E9-24** (submitted): against Precision defenders, lines committed at a floor of 0.9 failed 8.7% of the time with
  the scorer's weights and 3.5% with Gen 9's (house tables 5.0%). `reports/gen9-sid-weights-2026-11-13`.
- **X9** (G9-A10, submitted to will): the Gen 9 player on the 8X engine, `feature/gen9-x9` at ed2806f, card for card with
  the 8X bot when nothing is declared. E9-21 adopted and E9-20 rejected as worded (will, 08:27).
- **G9-S9** (submitted to will): knowing one partner honour could lower the defence's hand-over odds by 0.003 a position
  at the first defender decision with 8 and 7 cards (77% of what the whole layout would give); low weight.
  `reports/gen9-defender-bound-2026-11-13`.
- **E9-12 final** (written up by g9 from bill's boards; will to give the verdict): `9c-32` (card) +0.383 +- 0.085, `9x-32`
  (replay) +0.302 +- 0.082, `9u-32` (no auction reading) -0.010 +- 0.126 IMPs a board against `8p-32` on the precision
  book. `reports/gen9-e9-12-results-2026-11-13`.
- G9-A8 accepted by dave (08:36); the ladder shows `8p-32` and x8's five Gen 8 variants (will, 08:31); dave's population
  page (G9-D10) first version on `feature/gen9-population`.
- **Max, 09:03 UTC:** conditional claims are built in Gen 9 (X9), not by x8. Done: `feature/gen9-x9` ac7dfdb (floors,
  commitment, forks against the card without them; 17 tests), 7da02ba (`x9.prefer`, off by default; 19 tests).
- **X9 conditional-claims pilot 1** (G9-A11, sandbox, `9x3c-ft1` against `8x3c-ctl`, seed 9241, 400 boards, done 10:49;
  `reports/gen9-x9-conditional-2026-11-13`): the claims ran at 295 decisions, set floors at 36, committed 25 lines,
  restricted 117 later decisions and changed the played card 11 times on 8 boards; -0.0025 +- 0.0025 IMPs a board (one
  board lost 1 IMP, 399 flat); the 11 forks: none better, one worse; +1.9% time a board. The azure4 job `g9-x9-cond` is
  withdrawn (09:58). The sandbox restarted at about 10:23 and killed the run at 294 boards; it resumed from there.
- **Pilot 2** (`9x3p-ft1`, `prefer` 0.25, same deals, done 11:53): 13 played cards changed on 12 boards, -0.0075 +- 0.0056
  IMPs a board, +0.2% time. Both pilots: of 24 changed cards none gained and 3 gave up overtricks (4S made at both
  tables). G9-A11 submitted to will (12:00) with the recommendation: `x9.conditional` off by default, no box time.
- **E9-19, cheap version** (done 12:32, submitted; `reports/gen9-e9-19-2026-11-13`): every board of the Gen 9 cohort and
  of the Gen 8 pairs among `8s-32`, `8x3-32` and `71s-32` has the same auction at both tables (all bid with house-gen6),
  so those comparisons are card play only. On 2,322 Gen 8 native boards (439 with different contracts, all against
  Gen 1, Gen 5 or `8c-32`) the SD of the re-scored boards fell 29.6% (bar 30%), 12% over all boards, with mean shifts
  up to 1.7 IMPs a board; reported and stopped. Arena note 5.4 updated.
- **E9-25** queued on azure4 (job `e9-25`, 1 core, priority 3, validated by will 13:34): the cohort's two jobs hold all
  8 cores until the BEN pair ends (about 15 Nov 03:30 by the queue's estimate at 18:01); with conditional claims off in X9 it is not worth slowing the
  cohort, so it waits; due moved to 15 Nov 18:00. Job checkouts now fetch over public HTTPS (will, team/gen9 0122f15).
- **G9-B8 card intake, first version** (submitted 09:55; reviewer set to will at 18:10, since bill and sam are silent): `scripts/gen9_card_intake.py`; Max's two
  cards read into `configs/cards/intake/` with variants by seat and vulnerability, recorded agreements and the notes'
  style statements; results `reports/gen9-card-intake-2026-11-13`. The check sheets wait for Max's confirmation.
- **Freeze, 18:00 UTC.** The review page's Running and Team record were refreshed from
  `/home/claude/scratch/review/freeze.py` (sandbox): reviews 46, median 22 minutes from submission to verdict, longest
  2.8 hours; g9 gave 25, will 13, dave 4, sam 3, bill 1. Last log lines: sam 00:19, bill 04:02, dave 08:42 (last commit
  10:15), will 15:39 (messages to 17:52).

## Waiting

- **bill**: last seen 04:02 UTC. G9-B8's review moved to will (18:10); G9-B9, E9-13, G9-B5.
- **sam**: last seen 00:19 UTC. E9-4 and E9-6 leases expired; G9-S8 new.
- **dave**: last commit 10:15 UTC. Owns both cohort jobs; the disk decision is his until 08:00 UTC on 14 Nov (above).
- will's verdicts: G9-A11 accepted (13:37), E9-19 rejected (13:35).
- Verdicts (will, 10:06): E9-12 adopted (about +0.4 IMPs a board from reading a foreign system by its card; replay
  adds nothing, -0.08 +- 0.10), E9-24 inconclusive (post hoc; E9-25 registered), G9-A10 and G9-S9 accepted.
- E9-25: scripts on `feature/gen9` (`experiments/e9_25`, 9bb9aed); BEN's net is at
  `{home}/work/g9/ben/models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras` (will, 10:28); job queued (above).
- E9-22: the arrival records hold no card decisions; the guests' games must be played again first (logged 10:55).
  Exploratory instead, on the cohort's boards (`reports/gen9-newcomer-rows-2026-11-13`): the `8s-32` row predicts the
  newcomer `8p-32` 0.038 nats a decision better than v2's generic row (known bots' own rows gain 0.037 to 0.039); for
  `9a-32`, which randomizes among exactly equal cards, the house rows are 0.47 to 0.84 nats worse than generic. Arena note
  section 7: pick a newcomer's row from its play.
- dave: guest-b's native cost (-0.347 +- 0.160 in the arrival run), still open.
- E9-18 blocked on Max (a training box). E9-22 and E9-23 after the review package (their plumbing takes hours).
- Decisions for Max: the arena note's section 10; the card intake check sheets.
- G9-A5 base swap when Gen 8 lands on main; G9-A6 review package (g9): page final at the freeze; Max reviews from 01:00 UTC.

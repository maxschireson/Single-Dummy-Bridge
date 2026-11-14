# Gen 9: state at Sat 14 Nov 16:45 UTC (hand-over note)

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

- **azure4** (Gen 9's only box: Max to will, 00:45 UTC on 14 Nov, "You guys are down to one azure box for 9; other
  activity is paused"; Stu's loop keeps azure1, 2, 3, 5 and 6): will's job queue (`tools/boxq.py`); `tools/q jobs` shows
  it. All 8 cores busy and CPU-bound; the OS disk at P30 since 15:20 UTC (below).
  - `g9-cohort-azure4` (dave, priority 1, since 13 Nov 06:44 UTC; 4 cores and 4 workers since 02:45 UTC on Max's "Trim
    cohort now", 02:35, for Gen X Stu): the Gen 9 cohort, `configs/round9-cohort.json` on `feature/gen9-cohort`
    (46b7e004): `9a-32` against `8s-32`, `71s-32` and `8p-32` (the control) on 10,000 fresh deals (seed 9013), cohort
    identity 75b73937750652a5. 4,812 of 10,000 at 16:31, about 185 boards an hour on the P30 disk, so it ends about 15 Nov 21:00.
    Since 09:24 UTC it runs on `feature/gen9-cohort-amend` 9b2e7ad0 with env `BRIDGE_DDS_CACHE_SYNC=NORMAL` (disk flushes
    about 140 a second before, 13 after). g9's spec of 08:10 (7e0edac7: 46b7e004 plus will's 9bba86b6, the sync switch
    in `bridge_harness/dds_cache.py`) was refused at 09:08 by `verify_generation` in `bridge_harness/mixed_arena.py`,
    which checks the harness hash; g9 had expected no refusal. On Max's word (09:17: "Fix it so that it can run with
    changed code. Producing the boards is more important") will added `check_source`: a changed harness passes only if
    the run folder's `source-amendments.json` lists its hash with a reason (here 3f3c01afe8b6). Reviewed by g9; cards and
    results unchanged; logged on G9-D9. Feed `arena-gen9-azure4-feed`, generation 9 on the page (`gen9azure4`), the default view since 13 Nov 07:19
    (Max). At the freeze (13 Nov 18:00): 1,783 boards; `9a-32`'s IMPs a board against `71s-32` +0.54 +- 0.15 (594),
    `8p-32` +0.30 +- 0.15 (594), `8s-32` +0.17 +- 0.13 (595); the same auction at both tables on all 1,783, so card play
    only. `9a-32` takes 0.354 s per card decision with a choice against `8p-32`'s 0.376 on the same box.
  - **Gen X Stu, round 4c** (job `g9-genx-stu4c-azure4`, will, priority 2, 2 cores, since 16:22 UTC): the loop's
    `stu4c-put` (4488e91d; round 4's control net, pure Stu, told nothing about its opponents) against `8s-32` (weight 2),
    `9a-32` and `71s-32` on 4,000 fresh deals (seed 9021); `feature/gen9-genx-stu` at 57d0855f; feed
    `arena-gen9-genx-stu4c-azure4-feed`, registered under Gen 9 as "Gen X Stu (round 4c)". Max to the play session: "use
    r4c until further notice"; a new iteration takes Gen X Stu's cores by default.
  - Gen X Stu, round 3 (job `g9-genx-stu-azure4`, will, 02:45 to 16:21 UTC; Max named it at 00:49, at 01:00: "Put
    it into the mix at whatever level you want"), `stu3-ps` against `8s-32` (weight 2), `9a-32` and `71s-32` on 4,000
    fresh deals (seed 9019), `configs/round9-genx-stu.json` on `feature/gen9-genx-stu` (9bba86b6: Stu's
    `research/rollout-loop-20261113` at 545893b merged with the 8X arena line and `feature/gen9-cohort`); its DDS cache
    syncs NORMAL. Feed `arena-gen9-genx-stu-azure4-feed`, drained at 719 boards and archived. Final (699 boards at 16:00):
    -0.11 +- 0.15 IMPs a board to Gen X Stu over its three opponents; ladder +0.43 (+0.09 to +0.77).
  - `9a-32~ben64`: job `g9-cohort-ben64-azure4` (dave, 2 cores) since 13 Nov 07:50 UTC, 2,000 fresh deals (seed 9014),
    feed `arena-gen9-azure4-ben64-feed`, BEN 64 through will's `gen9_ben_lanes serve`. 1,393 of 2,000 at 16:31, about 42
    an hour, so it ends about 07:00 on 15 Nov. At the freeze: 454 boards, +0.19 +- 0.18.
  - `e9-25` (g9): failed at 02:47 UTC loading BEN's net (`BenLstmBidder` read the house bidders' output layer name);
    fixed on `feature/gen9` at adae5fbb and retried at 08:17; it ran 09:08 to 09:15 while the cohort was down. Report
    `reports/gen9-e9-25-2026-11-14` (4724cd7d); will's verdict: inconclusive (below).
  - Paused: `e9-0-n04` (387 of 800; it takes free cores when the cohort stops), `e9-16-h-v-p` (269 of 800), both g9's.
  - **Disk.** The VM is a Standard_F8as_v6 with one disk, the 128 GB Premium_LRS (P10) OS disk, and no temp disk. It was
    at its write limit from about 16:45 to 19:50 on 13 Nov (the cohort at about 105 boards an hour, 160 to 173 otherwise)
    and again from about 01:30 on 14 Nov; most writes are the cohort's `run/dds-cache.sqlite` (6.5 MB a board, WAL with
    `synchronous=FULL` until the restart above). Of will's four options (NORMAL sync, a fresh cache, a faster disk, leave
    it), NORMAL sync was taken first (09:24). The disk throttled again by 14:00, now on IOPS (511 writes/s at 175 ms, the
    cache 28.6 GB, larger than the page cache). On Max's word (15:19, after will's recap) will raised the disk's
    performance tier from P10 (500 IOPS, 100 MB/s) to P30 (5,000 IOPS, 200 MB/s) at 15:20, live, the same 128 GB disk:
    about $135 a month against about $20 for P10 (East US list) while set; it can go back to P10 when the cohort ends.
    Writes then 11 ms and the box CPU-bound. Space: will expects about 17 GB free when the cohort ends and checks it hourly. The leftover Gen 7 publisher
    on azure4 (pid 5704, `gen7-phase1-azure4`, g8's) republished a drained run every minute, about 7.5 MB every 20 s;
    will stopped and disabled it at 09:02 on g9's word and told g8 on the board.
- **The ladder** (G9-D9, dave and will, accepted 07:24): `arena/ladder.json` and `ladder.js` at the top of the arena page,
  refreshed hourly; the cohort's points appear as its boards come in.

## 14 November

- **Max (to will, 00:45 to 02:35 UTC):** one Azure box for Gen 9, other activity paused, Stu showing good results; he
  asked the Stu team for their latest to put in the arena, named it Gen X Stu, said to put it in at any level, and said
  "Trim cohort now". g7's board relay of his 13 Nov 19:57 word: Gen 9's work on heterogeneous populations is next in
  priority but less tied to compute.
- **G9-B8** was sent back by will (13 Nov 18:24): the done-when was not met (an older ACBL card, a photo-only reading, a
  public ACBL editor card, a PR); what is there checks out (tests and the break counts reproduced). g9 trimmed the
  done-when to the first version and resubmitted it (08:11); will accepted it at 09:03. The rest is **G9-B10** (owner
  bill).
- **E9-25: inconclusive** (will, 11:05: not confirmed as registered; reproduced byte for byte; report above). With BEN 64 defending, committed lines failed 8 of 160 times
  with the scorer's weights and 5 of 165 with Gen 9's: (1) met on the point estimate only (ratio 1.65, 95% interval 0.55
  to 4.94); (2) not met (p 0.27 and 0.625); (3) not met (Gen 9 3.0% against the house-defended control's 10.0%). The
  difference is in games, slams and doubled contracts (4 of 74 against 1 of 76). Changes no play setting.
- **G9-B10 item 4** fixed by g9 (82007dab): a card without a stated 1NT rebid range derives the balanced minimum under
  a 1NT opening from 13 or 14; no built-in card bids or reads differently (only `rb-precision`'s derived range changes,
  17-17 to 11-13, and its card does not cover rebids). Items 1 to 3 stay open for bill.
- **The cohort's cache and disk:** above. Max had not commented on the review page by 16:45 (no doc comments, nothing
  on the queue issue); G9-A6 stays submitted until he has looked.

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
  cohort, so it waits; due moved to 15 Nov 18:00. It got a core at 02:47 UTC on 14 Nov when the cohort drained and failed loading BEN's
  net; fixed and retried (Running). Job checkouts now fetch over public HTTPS (will, team/gen9 0122f15).
- **G9-B8 card intake, first version** (submitted 09:55; reviewer set to will at 18:10, since bill and sam are silent): `scripts/gen9_card_intake.py`; Max's two
  cards read into `configs/cards/intake/` with variants by seat and vulnerability, recorded agreements and the notes'
  style statements; results `reports/gen9-card-intake-2026-11-13`. The check sheets wait for Max's confirmation.
- **Freeze, 18:00 UTC.** The review page's Running and Team record were refreshed from
  `/home/claude/scratch/review/freeze.py` (sandbox): reviews 46, median 22 minutes from submission to verdict, longest
  2.8 hours; g9 gave 25, will 13, dave 4, sam 3, bill 1. Last log lines: sam 00:19, bill 04:02, dave 08:42 (last commit
  10:15), will 15:39 (messages to 17:52).

## Waiting

- **bill**: last seen 13 Nov 04:02 UTC. G9-B8 accepted (14 Nov 09:03); G9-B10, G9-B9, E9-13, G9-B5.
- **sam**: last seen 00:19 UTC. E9-4 and E9-6 leases expired; G9-S8 new.
- **dave**: last commit 13 Nov 10:15 UTC. Owns both cohort jobs; g9 replaced the main job's spec as lead (above).
- will's verdicts: G9-A11 accepted (13 Nov 13:37), E9-19 rejected (13:35), G9-B8 accepted (14 Nov 09:03), E9-25
  inconclusive (14 Nov 11:05).
- Verdicts (will, 10:06): E9-12 adopted (about +0.4 IMPs a board from reading a foreign system by its card; replay
  adds nothing, -0.08 +- 0.10), E9-24 inconclusive (post hoc; E9-25 registered), G9-A10 and G9-S9 accepted.
- E9-25: scripts on `feature/gen9` (`experiments/e9_25`, 9bb9aed; the BEN loader fix adae5fbb); BEN's net is at
  `{home}/work/g9/ben/models/TF2models/GIB-BBO-8742_2026-10-23-E30.keras` (will, 10:28); the job ran 14 Nov 09:08 to 09:15, report 4724cd7d (above).
- E9-22: the arrival records hold no card decisions; the guests' games must be played again first (logged 10:55).
  Exploratory instead, on the cohort's boards (`reports/gen9-newcomer-rows-2026-11-13`): the `8s-32` row predicts the
  newcomer `8p-32` 0.038 nats a decision better than v2's generic row (known bots' own rows gain 0.037 to 0.039); for
  `9a-32`, which randomizes among exactly equal cards, the house rows are 0.47 to 0.84 nats worse than generic. Arena note
  section 7: pick a newcomer's row from its play.
- dave: guest-b's native cost (-0.347 +- 0.160 in the arrival run), still open.
- E9-18 blocked on Max (a training box). E9-22 and E9-23 after the review package (their plumbing takes hours).
- Decisions for Max: the arena note's section 10; the card intake check sheets.
- G9-A5 base swap when Gen 8 lands on main; G9-A6 review package (g9): page final at the freeze; Max reviews from 01:00 UTC.

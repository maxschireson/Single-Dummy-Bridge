# Gen 9: state at Thu 12 Nov 23:25 UTC (hand-over note)

Written by g9 for whoever picks this up (a later g9 session, a helper, or Max). Everything here is on `feature/gen9`
or `team/gen9` unless a branch is named. Experiment files are `team/gen9:experiments/E9-*.md`; tasks are
`team/gen9:tasks/*.md`; `tools/workq.py` (on `team/gen9`) reads both.

## Dates

- Fri 13 Nov 18:00 UTC: freeze (no new runs started after it).
- Sat 14 Nov 01:00 UTC (Friday evening California): review package for Max (task G9-A6, g9).

## Running

- **azure4** (given by g8 at 14:59; no other box, no instance added): will's job queue (`tools/boxq.py`, deploy and
  update scripts on `team/gen9`). `tools/q jobs` shows it.
  - `d6-arrival` (dave, priority 1, all 8 cores): the arrival run. 5,117 of 6,200 boards at 23:15; ends about 00:45 to
    01:05 UTC. Failed once at 17:53 (rule bidder on an opponent's 3NT opening), fixed at 698679e on
    `feature/gen9-arena-arrival`, resumed on will's release at 18:55. Results on
    `transfer/gen9-d6-arrival-azure4-20261112`. Dave writes the page (items 1 to 6 of task G9-D6, beside the
    predictions registered there before the run).
  - Then, in order: `e9-0-n02` and `e9-0-n02e` (paused at about 600 of 800), `e9-0-n04`, `e9-16-r-v-p`,
    `e9-16-r-v-x` (priority 2); `e9-12-c`, `e9-12-u`, `e9-12-x` (bill's, priority 3); then priority 5 and 6 slices.
- **Sandboxes:** dave E9-17 (t-random, ends about 01:30); sam E9-6 bench (done 22:16).

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

## Decided

- The player model, the mixture over profiles and the rule for mixing kinds of profile row: `docs/gen9/architecture.md`
  (revised 12 Nov). The shell: `bridge_harness/gen9.py`; arrival and belief: `bridge_harness/player_model.py`.
- Readers are judged in tricks on stored solves first; a match only when the bench says it can be seen.
- Rules for the team (12 Nov): any lead other than the owner may give an experiment verdict 60 minutes after
  submission (workq applies it since 22:15); will releases a blocked request on a written check after 30 minutes of
  g9's silence. Module reviews between leads (bill with sam, dave with will).

## Waiting

- **bill has been silent since 11:16 UTC** (leases expired). His open items: E9-11 (verdict from the bench), E9-12
  (box jobs queued), E9-13, G9-B5. sam or will may take E9-11's bench verdict.
- PR #29 (arrival source into `feature/gen9`) after the run; PR #30 also carries unreviewed `signals-v2` (g9's call).
- E9-16 part 1d (which kinds of close decision, if any, are worth randomizing) and the box matches `e9-16-*`.
- Decision issues for Max: #23 (sub-agents), #24 (smallest promotable lead).
- G9-A5 base swap when Gen 8 lands on main; G9-A6 review package.

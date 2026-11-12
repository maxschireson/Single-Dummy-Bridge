# Population arena on one machine: registry, epochs and the boundary controller (G9-D4, 12 November 2026)

Gen 9 work in progress (dave). The design is [docs/gen9/arena.md](../../docs/gen9/arena.md); the
statistics are [docs/gen9/arena-statistics.md](../../docs/gen9/arena-statistics.md) as revised by
E9-5. Nothing here touches a collector, a feed, the registry on `gh-pages` or the dashboard.

## What exists

- **Player packages**, `configs/players/<id>.json` (`player-package-v1`), for six bots of the Gen 7
  capture capsule: `6-32`, `5RZ32` and `1` (anchors), `2`, `3`, and `7s-32` (Gen 6 fast with the
  gen7 engine and policy v4, as in `configs/gen9-proto-bots.json`). Each names its nets by sha256.
  A player's identity is its bundle without artifact paths, plus those hashes and its declaration,
  so the same nets under another folder are the same player (the published feeds give `1` and
  `5RZ32` two identities each for that reason; G9-D3).
- **Rules**, `configs/arena9/rules-v0.json` (A4's defaults with E9-5's changes: d = 0.1, cap 10,000;
  shares by purpose from the design note; epochs of 2,000 boards; a proposal, not adopted) and
  `rules-demo.json` (12-board epochs, for the demonstration only).
- **`bridge_harness/arena9.py`**: package checks (form, licence, declared lineage, no `oracle` key),
  the registry log and its fold into statuses, the schedule by purpose with the weight cap, epoch
  manifests named by the sha256 of their content, the boundary controller, and a synthetic backend.
- **`scripts/arena9.py`**: `init`, `queue` (how a person changes the arena), `run` (play, close,
  repeat) and `status`, with a `match` backend that plays real bots fork-free through
  `scripts/gen9_match.py`. That backend is the collectors' own `run_board`, with `meet` once a
  board and `auction_by` before each table. It refuses a package whose recorded artifact hashes
  are not the capsule bot's.

## What the controller does at a boundary

1. **Ratings.** A `ratings-v1` table per condition, from every board played so far, a deal family
   once per pair.
2. **Promotion tests.** Each open test is replayed in board order from its opening epoch with fresh
   capital. Reaching `K >= 20` writes `promote`. Futility or the cap writes `demote` (the candidate
   stays in the league).
3. **Admission.** A candidate whose strength SE is at most 0.15, or who has played 2,000 boards, is
   activated. An active player rated above the champion gets a promotion test.
4. **Retirement.** An unprotected active player whose interval lies more than 1.0 IMP below the
   champion, after the rules' minimum epochs, is retired.
5. **People's events.** Queued events are applied in file order and moved into the log. A
   `submit` whose package fails the checks is refused and left in the queue as `.refused`.
6. **Next epoch.** The experience snapshot is frozen at the boundary (`bridge_harness/experience_store.py`)
   and the next epoch is written, never over an existing one.

Every rule-made event carries `authority: rules <version>: <reason>` and its evidence: for a test,
the boards, `K` and `L`; for a retirement, the gap and its SE.

## Tests (`tests/test_arena9.py`, 10, numpy only, about 1 s)

- **Packages:** checks, including refusal of an oracle bot. Identity ignores artifact paths but not
  artifact hashes or settings.
- **First epoch:** admission, panel and training pairs as designed.
- **Life of an epoch:** it is played and closed, can't close before its boards are in, and is never
  overwritten.
- **Determinism:** the next epoch's id is the same from two control directories with the same inputs.
- **Arrival and departure:** a queued `submit` and `retire` between epochs give an epoch with the
  new player in admission and the retired one gone, with no code change.
- **Refusals:** a queued oracle or unknown package is refused.
- **Weight cap:** weights don't more than double or halve unless the pair's purpose changed.
- **Retirement:** a player 3 IMPs weaker is retired by rule, and anchors are not.
- **Promotion:** a candidate 1 IMP stronger is admitted, then tested, then promoted, and the old
  champion stays in the league.

On synthetic boards (8 epochs of 2,000, a candidate 0.4 IMPs better in play and 0.1 in bidding, a
player 2.5 worse):

- Epoch 5: the better candidate is admitted (578 boards, SE 0.148) and its promotion test opens
  from epoch 6.
- From epoch 6 the test pair gets its 20% share, 400 boards an epoch.
- Epoch 7: the weak player is admitted (939 boards, SE 0.144).
- Epoch 8: the candidate is promoted after 825 test boards (`K` = 21.0), and the weak player is
  retired by rule at 2.51 below the champion (SE 0.11).
- Epoch 9 runs with the new champion.

## Demonstration with real bots

Two-core sandbox, fork-free, 32 samples, fresh seeded deals (`demo-control/`, `demo-run.log`).

- `init`: champion `6-32`, anchors `5RZ32` and `1`, candidate `3`. Epoch 1's schedule:
  - admission: `3` against `6-32`, `5RZ32` and `1`;
  - panel: `6-32` against both anchors;
  - training: `6-32` self-play.
- A person queues two events: `submit 7s-32` (an arrival) and `retire 3` (a departure).
- `run --epochs 2 --backend match`:
  - Epoch 1 plays its 12 boards with the real bots.
  - At the boundary the two events are applied and epoch 2 is derived from epoch 1 (`previous` is
    epoch 1's id). Its roster is `6-32`, `5RZ32`, `1` and `7s-32`, with `7s-32` in admission.
  - Epoch 2 plays its 12 boards (80 s) and epoch 3 opens.
- Nothing was typed between epochs and no code changed.

What the demonstration does not show:

- **No rule fired on real bots.** At 12 boards an epoch no statistical rule can, so the departure
  was a person's queued `retire`. Rule-made admissions, promotions and retirements are shown on
  synthetic boards above.
- **One slot only.** Several collectors sharing an epoch, each claiming a slot by a push, is not
  built yet.
- **BEN** players need a server and were left out.
- The first attempt stopped on a missing `h5py` (the bidders need it), and the second at the first
  self-play pair, because `run_board` wants two distinct roster ids. Both are fixed: the
  self-play roster's second id is the audit reference bot, which never sits. The epoch did not
  close and no row was lost; the run resumed after the boards already written.

## Not done

- Slots claimed by push on a control branch, and a follower beside an existing collector
  (phase 0 of the design note), are G9-D6 and later.
- Experience envelopes are merged and snapshotted at each boundary, but no reader writes them yet.
- The field mix and the rules version are decisions for Max.

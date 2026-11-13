# For the loop's dashboard

Max (13 November, 09:30 UTC): another session builds a dashboard for this loop, apart from the arena's, on what needs
watching here. This page is the loop session's side of that: where the data is, what each run is, what to compute,
and what the numbers must not be read as. The loop session keeps it current. Ask on the board (`box/coordination`,
`BOARD.md`, entries signed `loop`).

## Where the data is

| What | Where |
| --- | --- |
| The runs and what each is | `training/rollout-loop-20261113/runs.json` on `research/rollout-loop-20261113` (written by `make_runs.py` from the job files; it changes when the plan changes) |
| Rows, summaries, logs of a box | `transfer/rollout-loop-azure3-20261113`, `transfer/rollout-loop-azure5-20261113`: a commit about every ten minutes while anything changed |
| The sandbox matches of 13 November | `transfer/rollout-loop-sandbox-20261113` (finished; `summary.txt` has the tables) |
| A box's health | `box/azure3/status`, `box/azure5/status`: `heartbeat.json` (time, load, memory, disk, top processes), replaced at least every five minutes |
| Decisions, reasons, who holds which box | the board |

On a box's transfer branch:

- `<run>/results.jsonl`: one line a finished board, in order of finishing, not of deal. `<run>/summary.json` and
  `<run>/manifest.json` beside it. `<run>/EPISODES.txt` where full records are kept on the box (they are not published).
- `<run>.log`: the match's own progress lines. `runs.log`: one `start` line and one `end` line a job, with the source
  commit. A job stopped by hand has no `end` line or a non-zero exit.

A row of `results.jsonl`:

| Field | Meaning |
| --- | --- |
| `index` | The deal's number. Deals are a function of (seed, index): the same seed and index is the same deal in any run |
| `common` | IMPs to the **first-named** bot of the pair, the deal bid once by the common bidder and played at two tables with the seats swapped: card play only. This is the number to use |
| `native` | The same with each side bidding for itself; equal to `common` here, since every bot bids alike |
| `contract`, `family` | The contract played; the deal's family hash |
| `cpu` | CPU seconds for the board, both tables |
| `search.candidate.x8`, `search.opponent.x8` | For an 8X-engine bot (every Stu-family bot), counts over the board's two tables: decisions made by `rollout`, `blend`, `claim`; `moved` (rollout decisions whose card is not the table net's first choice); `guaranteed`, `guarantee_moved`, `odds`, `mixed`; `rollouts`, `net_rows`, `seconds`. `candidate` is the first-named bot |

## The roles in `runs.json`

| Role | What it is | Worth showing | Not to be read as |
| --- | --- | --- | --- |
| `collection` | Stu against itself (two ids of one bot) on training deals, full records kept: a round's games | Boards done against `deals` and against the round's cut (below), boards an hour, failures (the log's `N failed`), CPU a board, the decision mix | Strength. `common` is one bot against itself: its mean is a check (it should sit within noise of 0), nothing more. A run with `tables_a_board: 1` in `runs.json` (`sp0`, `sp0b`: one table a board, since 12:00 UTC on 13 November) has `common: null` and `tables: 1` in every row: count boards and CPU only |
| `ladder` | A bot of the Stu family against Gen 8 card play (`8p-32-v41`) on the gate's first 500 deals (a first pass of 200 deals a rung, then the rest: `passes` in `runs.json`). `first_bot.net` is the net inside (`v2`, `v1`, later a round's own), `first_bot.rung` where rollouts take over (`runs.json` `rungs`) | A table, rung by net: mean of `common` +- standard error, boards. Beside it the paired differences below | A ranking of nets against people or against other bots: it is each bot against this one opponent |
| `gate` | A round's Stu against Gen 8 card play on the gate's deals | By round: mean +- standard error, boards; the paired difference between consecutive rounds | |
| `data` | Ladder bots against Stu on training deals, for rows the collection lacks (rollout decisions at early tricks) | Boards done. Its `common` (the first-named bot against Stu) only with the warning beside this table | A measure of the rung: a rollout bot is the opponent Stu's net models best, which flatters Stu |
| `control` | The leverage control (README, "Measured before round 0") at ten times the deals | The 2 by 2 table as in the README | |
| `preflight` | Two to six boards to check a bot runs | Nothing | |

## What to compute

- **Mean and standard error** of `common` over a run's rows: boards are independent, so the error is the standard
  deviation over the square root of the count. Show the count. Under about 200 boards say "interim".
- **Paired difference** of two runs with the same seed: over the `index` values both have, the mean and standard
  error of the row-by-row difference of `common`. Use it for rung against the `stu` rung of the same net, v2 against v1
  at the same rung, and one round's gate against the last round's. It is much tighter than the difference of two
  means. Runs with different seeds cannot be paired.
- **The round's cut.** Round 0's collection is the runs with role `collection` and round 0 (`s0`, `s0b`, `r0`).
  `runs.json` `rounds` says what is waited for. Since 10:12 UTC on 13 November no board count is: a learning curve
  (PLAN.md) showed that waiting for 6,000 boards buys almost nothing, so round 1's set is cut when its training chain
  is ready, and the collection goes on for later rounds. Show the total and the rate; the loop session posts the cut
  (time and boards) on the board when it happens.
- **Decision mix** for a Stu-family bot in a run: per board, `rollout`, `blend` and `claim` decisions, and `moved`
  over `rollout`.
- **Health:** the age of each box's heartbeat and of each transfer branch's last commit; a collection whose row count
  has not moved in 20 minutes while its box's heartbeat is fresh needs looking at.

## Standing cautions to print with the numbers

- **Seed 131 is the gate's and the ladder's and is never trained on. Seed 9001 is round 0's training seed.** A run on a
  training seed says nothing about strength on fresh deals once a net has been trained on it.
- **New Stu against old Stu is not the gate.** A net trained on a bot's games predicts that bot, and in the control
  the inside net matching the opponent was worth +1.12 +- 0.16 IMPs a board by itself. The gate is the outside
  opponent.
- Everything here is against one outside opponent, Gen 8 card play. Reference from the 8X session, same opponent and
  seed: x8's 8Z (which is the rung `stu` with net `v1`) -0.38 +- 0.14 over 541 boards, with feature forks on.

## Added 13 November, 12:00 UTC

- **Rungs `pure-sl` and `pure-rl`** (runs `l0-pl`, `l0-pr`; `runs.json` `rungs` has the text): pure Stu with a searched
  opening lead and with the lead from rollouts. Compare each with the rung `pure` (`l0-p`) by deal: the three differ
  only in the opening lead.
- **Lead rollouts in a row:** where a bot rolled out an opening lead, its `x8` summary also has `lead` (leads rolled
  out on the board), `lead_moved` (of them, not the net's first choice) and `lead_seconds`. They are counted under
  `rollout` too. Rows of bots without it lack the keys.
- **Why the collection changed:** two ids of one bot played the same cards at both tables of a board (same seed by ply
  and seat), so in `s0`, `s0b` and `r0` a board is one distinct table played twice. For those runs, boards is the
  honest count of distinct tables. From `sp0` on a board is one table and costs about half the CPU.

## Coming, not there yet

- Training: when round 1 trains (planned on azure5), its `metrics.json` (one record an epoch: held-out log-loss and
  agreement with the bot's card, by bot; regret and `rated_pick` on rated cards) will be published under `train-r1/`
  on azure5's transfer branch. The loop session will add the field list here then.
- Round 1's bots (`stu1a`, `stu1b` and their rungs) and runs will appear in `runs.json` with `round` 1.

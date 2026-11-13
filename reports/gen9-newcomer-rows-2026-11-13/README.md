# A newcomer's row in rollout net v2: generic against the nearest known bot (exploratory, beside E9-22), 13 November 2026

g9. This is not E9-22's registered test. E9-22 names the arrival run's guests, and those records hold no card decisions
(logged on E9-22). This exploratory analysis uses the Gen 9 cohort's boards instead.

## What was measured

- **Net and data.** Rollout net v2 (`transfer/rollout-net-v2-20261113`, `runs/w768/policy_epoch5.npz`, SHA-256
  `8f87aa8f…`) on the cohort's first 970 boards, both tables. These were the boards published at 12:30 UTC on
  `arena-gen9-azure4-feed`.
- **Bots.** Two are newcomers to v2, which never saw them: `9a-32` and `8p-32`. Two it knows: `8s-32` and `71s-32`,
  the control.
- **Decisions scored.** Every card decision with a choice by the bot in question, as the deciding side (declarer plays
  dummy's cards too). Each is scored as the log-loss of the card the bot played, in nats a decision.
- **Rows.** The deciding side's row varies: generic (row 0, what v2 gives an unknown name), `8s-32`, `71s-32` or
  `6-32`. The other side's row is its own when v2 knows that bot, else generic.

Script: `e922x.py`. Results: `cohort-all.json`. Per-decision losses were kept in g9's sandbox.

## Results

Log-loss by row; the paired difference from the generic row is in brackets.

| Bot (opponent) | Decisions | Generic | `8s-32` row | `71s-32` row | `6-32` row |
| --- | ---: | ---: | ---: | ---: | ---: |
| `8s-32`, known (`9a-32`) | 13,264 | 0.553 | 0.514 (-0.039 +- 0.002) | 0.514 (-0.039) | 0.550 (-0.003) |
| `71s-32`, known (`9a-32`) | 13,441 | 0.566 | 0.529 (-0.037 +- 0.002) | 0.529 (-0.037) | 0.564 (-0.002) |
| `8p-32`, newcomer (`9a-32`) | 13,293 | 0.567 | 0.529 (-0.038 +- 0.002) | 0.529 (-0.038) | 0.565 (-0.002) |
| `9a-32`, newcomer (`71s-32`) | 13,348 | 1.863 | 2.334 (+0.471 +- 0.009) | 2.346 (+0.483) | 1.924 (+0.061) |
| `9a-32`, newcomer (`8p-32`) | 13,242 | 1.785 | 2.403 (+0.618 +- 0.011) | 2.418 (+0.633) | 1.971 (+0.187) |
| `9a-32`, newcomer (`8s-32`) | 13,271 | 1.358 | 2.195 (+0.837 +- 0.014) | 2.314 (+0.956) | 1.850 (+0.492) |

How fast the right row shows: the cumulative log-likelihood ratio between the `8s-32` row and the generic row passes
3 nats after 112 to 156 decisions for the three house-like bots, which is a few boards. For `9a-32` it passes 3 nats
the other way after 3 or 4 decisions.

## Reading

- **A newcomer that plays like a known bot.** `8p-32` is the Gen 8 prototype. The nearest known row predicts its cards
  0.038 nats a decision better than the generic row. That is as much as a known bot's own row gains (0.037 to 0.039).
  E9-22's registered bar for a newcomer was 0.02, so on this population it would be met. The registered control
  figure of about 0.10 nats is wrong: a known bot's own row gains about 0.04 here.
- **A newcomer that randomizes.** `9a-32` plays a random one of its exactly equal-best cards (the cohort's model note).
  - v2 was trained on bots that pick among equal cards by a fixed rule. It predicts `9a-32` far worse: 1.4 to 1.9
    nats, against about 0.55.
  - A house row makes this worse by 0.47 to 0.84 nats.
  - Much of that loss is spent on exactly equal cards, which change nothing double dummy. So a rollout's results
    suffer far less than the loss suggests; that part was not measured here.
- **What this means for the arena note.** Section 7 should choose a newcomer's row from its play, not from its declared
  system. A few boards of its decisions pick the row: by the likelihood of each candidate row, with the generic row
  kept while nothing fits. A bot that randomizes among equal cards, as Gen 9 and 8X now do, needs a row trained on such
  play, or a model that does not try to predict which equal card it plays.

# Gen 9 status

Generated 2026-11-12 07:38 UTC by `tools/workq.py` after a change by `sam`. Do not edit by hand. How to work here: [README.md](README.md).

## Tasks by owner

| Owner | leased | submitted | blocked | open | proposed | resolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bill | 3 | 0 | 0 | 1 | 0 | 2 |
| dave | 1 | 0 | 0 | 1 | 0 | 4 |
| g9 | 0 | 0 | 1 | 3 | 0 | 3 |
| pool | 0 | 0 | 0 | 1 | 0 | 0 |
| sam | 2 | 1 | 0 | 1 | 0 | 3 |
| will | 0 | 0 | 1 | 1 | 0 | 4 |

## Waiting for review

| Reviewer | Id | Title | Submitted by | Branch |
| --- | --- | --- | --- | --- |
| g9 | [G9-S6](tasks/G9-S6.md) | The house bots' own carding, measured | sam | feature/gen9-signals |

## Tasks

| Id | Title | Owner | Holder | State | Priority | Due | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [G9-B3](tasks/G9-B3.md) | E9-1: what the filter recovers on systems the scorer never saw | bill | bill until 11-12 11:16 | leased | high | 2026-11-13T02:00Z |  |
| [G9-D4](tasks/G9-D4.md) | Registry, epoch manifest and a one-machine epoch runner | dave | dave until 11-12 11:33 | leased | high | 2026-11-13T14:00Z |  |
| [G9-S4](tasks/G9-S4.md) | E9-4: reading gain against carding bots, by honesty and scheme | sam | sam until 11-12 11:22 | leased | high | 2026-11-13T04:00Z |  |
| [G9-B4](tasks/G9-B4.md) | Card to profile distance and system detection | bill | bill until 11-12 11:30 | leased | medium | 2026-11-13T10:00Z |  |
| [G9-B6](tasks/G9-B6.md) | Three real cards read into the IR, each with its check sheet | bill | bill until 11-12 11:30 | leased | medium | 2026-11-13T18:00Z |  |
| [G9-S5](tasks/G9-S5.md) | Honesty and play-factor estimators; learning curve by boards seen | sam | sam until 11-12 11:27 | leased | medium | 2026-11-13T12:00Z |  |
| [G9-S6](tasks/G9-S6.md) | The house bots' own carding, measured | sam | sam | submitted | medium | 2026-11-13T16:00Z |  |
| [G9-A5](tasks/G9-A5.md) | Base swap: replace the Gen 8 snapshot when Gen 8 is on main | g9 |  | blocked | medium |  |  |
| [G9-W5](tasks/G9-W5.md) | Box job queue and results convention for Gen 9 experiments | will |  | blocked | medium |  |  |
| [G9-A3](tasks/G9-A3.md) | Gen 9 player shell with reader hooks and the mixture over profiles | g9 |  | open | high | 2026-11-12T18:00Z |  |
| [G9-A6](tasks/G9-A6.md) | Review package for Max | g9 |  | open | high | 2026-11-14T01:00Z |  |
| [G9-A7](tasks/G9-A7.md) | E9-0: what a nat of reading is worth | g9 |  | open | high | 2026-11-13T06:00Z | after G9-A3 |
| [G9-S7](tasks/G9-S7.md) | E9-6: what agreed signals are worth to the house pair | sam |  | open | high | 2026-11-13T10:00Z |  |
| [G9-X1](tasks/G9-X1.md) | E9-7: a reading model for BEN from recorded boards | pool |  | open | high | 2026-11-13T12:00Z |  |
| [G9-W4](tasks/G9-W4.md) | Queue metrics: are there too few thinkers or too few executors | will |  | open | medium | 2026-11-13T12:00Z |  |
| [G9-B5](tasks/G9-B5.md) | Scorer trained with dropped calls; handing misread calls to the rules | bill |  | open | low | 2026-11-13T18:00Z | after G9-B3 |
| [G9-D6](tasks/G9-D6.md) | A small arena on a box with synthetic players | dave |  | open | low | 2026-11-13T18:00Z | after G9-D4 |
| [G9-A1](tasks/G9-A1.md) | Architecture v0 and work plan | g9 |  | resolved | high | 2026-11-12T08:00Z | accepted |
| [G9-A2](tasks/G9-A2.md) | Player model, table contract and experience schema | g9 |  | resolved | high | 2026-11-12T12:00Z |  |
| [G9-A4](tasks/G9-A4.md) | Rating, field score and promotion test: the statistics | g9 |  | resolved | high | 2026-11-12T14:00Z | accepted |
| [G9-B1](tasks/G9-B1.md) | Design note: card IR for bidding, card to rules, the rule filter | bill | bill | resolved | high | 2026-11-12T12:00Z | accepted |
| [G9-B2](tasks/G9-B2.md) | Rule filter: the card as a scorer over hand types | bill | bill | resolved | high | 2026-11-12T17:00Z | accepted |
| [G9-D1](tasks/G9-D1.md) | Design note: the arena as a population | dave |  | resolved | high | 2026-11-12T12:00Z | accepted |
| [G9-D2](tasks/G9-D2.md) | E9-5: arena simulator; schedule and promotion rule against fixed pairs | dave | dave | resolved | high | 2026-11-13T02:00Z | accepted |
| [G9-S1](tasks/G9-S1.md) | Design note: signals as executable rules, the class rule, carding bots, estimators | sam | sam | resolved | high | 2026-11-12T12:00Z | accepted |
| [G9-S2](tasks/G9-S2.md) | Signal model and carding bots | sam | sam | resolved | high | 2026-11-12T18:00Z | accepted |
| [G9-S3](tasks/G9-S3.md) | E9-3: how often spots nine and below are not equivalent | sam | sam | resolved | high | 2026-11-12T20:00Z | accepted |
| [G9-W1](tasks/G9-W1.md) | Design note: work queue and experiment registry for a project that never stops | will | will | resolved | high | 2026-11-12T12:00Z | accepted |
| [G9-W2](tasks/G9-W2.md) | `workq`: lease, renew, submit, resolve from the command line | will | will | resolved | high | 2026-11-12T16:00Z | accepted |
| [G9-D3](tasks/G9-D3.md) | Rating table fitted to the published Gen 5 to Gen 7 feeds | dave | dave | resolved | medium | 2026-11-13T06:00Z | accepted |
| [G9-D5](tasks/G9-D5.md) | Experience store: per-board deltas, merge, epoch snapshot | dave | dave | resolved | medium | 2026-11-13T12:00Z | accepted |
| [G9-W3](tasks/G9-W3.md) | One command to prepare an environment and run the Gen 9 tests | will | will | resolved | medium | 2026-11-12T20:00Z | accepted |
| [G9-W6](tasks/G9-W6.md) | Script for the base swap | will | will | resolved | medium | 2026-11-12T22:00Z | accepted |

## Experiments

| Id | Title | Owner | Holder | State | Priority | Due | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [E9-1](experiments/E9-1.md) | What the rule filter recovers on systems the scorer never saw | bill | bill until 11-12 11:16 | leased | high | 2026-11-13T02:00Z |  |
| [E9-4](experiments/E9-4.md) | Reading gain against carding bots, by honesty and scheme | sam | sam until 11-12 11:27 | leased | high | 2026-11-13T04:00Z |  |
| [E9-2](experiments/E9-2.md) | Boards needed to identify a system from finished boards | bill | bill until 11-12 11:30 | leased | medium | 2026-11-13T10:00Z |  |
| [E9-9](experiments/E9-9.md) | The house bots' own carding, measured against declared schemes | sam | sam until 11-12 08:38 | leased | medium |  |  |
| [E9-0](experiments/E9-0.md) | What a nat of reading is worth: IMPs against log weight of the true layout | g9 |  | open | high | 2026-11-13T06:00Z | after G9-A3 |
| [E9-6](experiments/E9-6.md) | What agreed signals are worth to the house pair | sam |  | open | high | 2026-11-13T10:00Z |  |
| [E9-7](experiments/E9-7.md) | A reading model for BEN from recorded boards | pool |  | open | high | 2026-11-13T12:00Z |  |
| [E9-8](experiments/E9-8.md) | What replaying the bidder is worth over the hand-fit scorer | bill |  | open | high | 2026-11-12T12:00Z |  |
| [E9-3](experiments/E9-3.md) | How often spot cards nine and below are not equivalent | sam | sam | resolved | high | 2026-11-12T20:00Z | adopted. **The class rule holds.** Defenders' spots (two to nine) in the suit played do not all take the same number of tricks on the true deal in **1.49% ± 0.08%** of 21,057 decisions (prediction: at most 5%). When they differ, the worst spot costs 1.13 tricks on average; the lowest spot is among the best in 99.2% of all decisions |
| [E9-5](experiments/E9-5.md) | Arena simulator: schedule and promotion rule against fixed pairs | dave | dave | resolved | high | 2026-11-13T02:00Z | adopted. Kind of evidence: simulation. Report, data and code: `reports/gen9-arena-sim-2026-11-12/README.md` on |

## Agents

| Agent | Role | Last seen | Unread | Session |
| --- | --- | --- | ---: | --- |
| bill | bidding systems lead | 11-12 07:30 | 16 | [link](https://claude.ai/code/session_01N2EvxBFvnAqv6K35NaR2Rp) |
| dave | Dynamic arena lead | 11-12 07:32 | 2 | [link](https://claude.ai/code/session_01N2EvxDBkJm2K1K7MDW4c3n) |
| g9 | Gen 9 architect and lead (Claude Fable 5.2) | 11-12 07:24 | 1 | [link](https://claude.ai/code/session_01N2EvxCJBUzzHdcpohDTBew) |
| sam | Signalling and card-play reading lead | 11-12 07:34 | 4 | [link](https://claude.ai/code/session_01N2EvxBLh2BH7Y2HHdEY5Qy) |
| will | Workflow and infrastructure lead | 11-12 07:24 | 1 | [link](https://claude.ai/code/session_01N2EvxCeTswS4ptZevoA7dH) |

## Latest messages

| To | From | Sent | First line |
| --- | --- | --- | --- |
| g9 | sam | 11-12 07:37 | [G9-S6 submitted for your review: The house bots' own carding, measured](inbox/g9/20261112T0737Z-sam-g9-s6-submitted-for-your-revie.md) |
| sam | g9 | 11-12 07:37 | [Your 2a6a325 is folded in too (feature/gen9); the three-array signal_row stands](inbox/sam/20261112T0737Z-g9-your-2a6a325-is-folded-in-too.md) |
| will | g9 | 11-12 07:37 | [G9-W6 resolved (accepted): Script for the base swap](inbox/will/20261112T0737Z-g9-g9-w6-resolved-accepted-script.md) |
| dave | g9 | 11-12 07:37 | [G9-D3 resolved (accepted): Rating table fitted to the published Gen 5 to Gen 7 feeds](inbox/dave/20261112T0737Z-g9-g9-d3-resolved-accepted-rating.md) |
| all | g9 | 11-12 07:35 | [The Gen 9 player is on feature/gen9 (4f12d51): calls, cards and the table contract in one place](inbox/all/20261112T0735Z-g9-the-gen-9-player-is-on-feature.md) |
| sam | g9 | 11-12 07:35 | [S2 accepted and merged, folded into the shell; what changed in your files](inbox/sam/20261112T0735Z-g9-s2-accepted-and-merged-folded.md) |
| sam | g9 | 11-12 07:35 | [G9-S2 resolved (accepted): Signal model and carding bots](inbox/sam/20261112T0735Z-g9-g9-s2-resolved-accepted-signal.md) |
| bill | will | 11-12 07:33 | [Heads-up: Gen 8's rule bidder r2 (after the snapshot) super-accepts transfers; 5 card tests fail on it](inbox/bill/20261112T0733Z-will-heads-up-gen-8-s-rule-bidder-r.md) |
| g9 | will | 11-12 07:33 | [G9-W6 submitted for your review: Script for the base swap](inbox/g9/20261112T0733Z-will-g9-w6-submitted-for-your-revie.md) |
| will | dave | 11-12 07:32 | [G9-W3 resolved (accepted): One command to prepare an environment and run the Gen 9 tests](inbox/will/20261112T0732Z-dave-g9-w3-resolved-accepted-one-co.md) |
| g9 | sam | 11-12 07:30 | [For your fold of G9-S2: one more commit on feature/gen9-signals (2a6a325); please fold from it, not f854cfe](inbox/g9/20261112T0730Z-sam-for-your-fold-of-g9-s2-one-mor.md) |
| g9 | dave | 11-12 07:29 | [G9-D3 submitted for your review: Rating table fitted to the published Gen 5 to Gen 7 feeds](inbox/g9/20261112T0729Z-dave-g9-d3-submitted-for-your-revie.md) |
| will | g9 | 11-12 07:28 | [W1 and W2 accepted; W3 to dave for review; build the pinned issue for Max; module reviews move to peers](inbox/will/20261112T0728Z-g9-w1-and-w2-accepted-w3-to-dave.md) |
| sam | g9 | 11-12 07:28 | [S1 accepted and merged; E9-3 adopted; S2 is being folded into the player shell by me](inbox/sam/20261112T0728Z-g9-s1-accepted-and-merged-e9-3-ad.md) |
| dave | g9 | 11-12 07:28 | [Please review G9-W3 (PR 20, will's test runner) and merge it into feature/gen9 if it is right](inbox/dave/20261112T0728Z-g9-please-review-g9-w3-pr-20-will.md) |

## Boxes

Heartbeats from `box/<box>/status` and the allocation table on `box/coordination` (which decides who holds a box), read at 11-12 07:06 UTC by `workq.py fleet`.

| Box | Heartbeat | Load / CPUs | Free memory | Free disk | boxctl queue | Board says |
| --- | --- | --- | --- | --- | --- | --- |
| azure1 | 11-12 07:02 | 8.06 / 8 | 20.5 of 31.3 GB | 121.4 GB | idle | g8: Gen 8 experiments, since 03:50 UTC. Also holds the Azure CLI and the timers that end a... |
| azure2 | 11-12 07:03 | 6.21 / 8 | 21.6 of 31.3 GB | 113.5 GB | idle | g7: Gen 7.1, `71s-32` against `7s-32` on every board, eight workers, deals v4.1 was not tr... |
| azure3 | 11-12 07:02 | 8.66 / 8 | 18.5 of 31.3 GB | 111.6 GB | idle | g7: Gen 7.1, `71s-32` against BEN (64), eight lanes, deals v4.1 was not trained on, since ... |
| azure4 | 11-12 07:02 | 8.24 / 8 | 24.7 of 31.3 GB | 109.6 GB | idle | g8: Gen 8 experiments, since 03:50 UTC |
| azure5 | 11-12 07:06 | 6.31 / 8 | 23.5 of 31.3 GB | 109.0 GB | idle | p41: Gen 8 tasks from g8 (Max, 06:32 UTC); until about 07:20 UTC also the last run of poli... |
| azure6 | 11-12 07:03 | 8.08 / 8 | 20.9 of 31.3 GB | 125.7 GB | idle | g8: Gen 8 experiments. No longer temporary (Max, 06:03 UTC): `g8-azure6-stop.timer` on azu... |

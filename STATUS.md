# Gen 9 status

Generated 2026-11-12 06:54 UTC by `tools/status.py` from the task and experiment files. Do not edit by hand.

## Tasks by owner

| Owner | leased | submitted | blocked | open | proposed | resolved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| bill | 1 | 0 | 0 | 5 | 0 | 0 |
| dave | 1 | 0 | 0 | 5 | 0 | 0 |
| g9 | 1 | 0 | 1 | 4 | 0 | 1 |
| pool | 0 | 0 | 0 | 1 | 0 | 0 |
| sam | 1 | 0 | 0 | 6 | 0 | 0 |
| will | 1 | 0 | 1 | 4 | 0 | 0 |

## Tasks

| Id | Title | Owner | Holder | State | Priority | Due | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [G9-A2](tasks/G9-A2.md) | Player model, table contract and experience schema | g9 | g9 | leased | high | 2026-11-12T12:00Z |  |
| [G9-B1](tasks/G9-B1.md) | Design note: card IR for bidding, card to rules, the rule filter | bill | bill | leased | high | 2026-11-12T12:00Z |  |
| [G9-D1](tasks/G9-D1.md) | Design note: the arena as a population | dave | dave | leased | high | 2026-11-12T12:00Z |  |
| [G9-S1](tasks/G9-S1.md) | Design note: signals as executable rules, the class rule, carding bots, estimators | sam | sam | leased | high | 2026-11-12T12:00Z |  |
| [G9-W1](tasks/G9-W1.md) | Design note: work queue and experiment registry for a project that never stops | will | will | leased | high | 2026-11-12T12:00Z |  |
| [G9-A5](tasks/G9-A5.md) | Base swap: replace the Gen 8 snapshot when Gen 8 is on main | g9 |  | blocked | medium |  |  |
| [G9-W5](tasks/G9-W5.md) | Box job queue and results convention for Gen 9 experiments | will |  | blocked | medium |  |  |
| [G9-A3](tasks/G9-A3.md) | Gen 9 player shell with reader hooks and the mixture over profiles | g9 |  | open | high | 2026-11-12T18:00Z |  |
| [G9-A4](tasks/G9-A4.md) | Rating, field score and promotion test: the statistics | g9 |  | open | high | 2026-11-12T14:00Z |  |
| [G9-A6](tasks/G9-A6.md) | Review package for Max | g9 |  | open | high | 2026-11-14T01:00Z |  |
| [G9-A7](tasks/G9-A7.md) | E9-0: what a nat of reading is worth | g9 |  | open | high | 2026-11-13T06:00Z |  |
| [G9-B2](tasks/G9-B2.md) | Rule filter: the card as a scorer over hand types | bill |  | open | high | 2026-11-12T17:00Z |  |
| [G9-B3](tasks/G9-B3.md) | E9-1: what the filter recovers on systems the scorer never saw | bill |  | open | high | 2026-11-13T02:00Z |  |
| [G9-D2](tasks/G9-D2.md) | E9-5: arena simulator; schedule and promotion rule against fixed pairs | dave |  | open | high | 2026-11-13T02:00Z |  |
| [G9-D4](tasks/G9-D4.md) | Registry, epoch manifest and a one-machine epoch runner | dave |  | open | high | 2026-11-13T14:00Z |  |
| [G9-S2](tasks/G9-S2.md) | Signal model and carding bots | sam |  | open | high | 2026-11-12T18:00Z |  |
| [G9-S3](tasks/G9-S3.md) | E9-3: how often spots nine and below are not equivalent | sam |  | open | high | 2026-11-12T20:00Z |  |
| [G9-S4](tasks/G9-S4.md) | E9-4: reading gain against carding bots, by honesty and scheme | sam |  | open | high | 2026-11-13T04:00Z |  |
| [G9-S7](tasks/G9-S7.md) | E9-6: what agreed signals are worth to the house pair | sam |  | open | high | 2026-11-13T10:00Z |  |
| [G9-W2](tasks/G9-W2.md) | `workq`: lease, renew, submit, resolve from the command line | will |  | open | high | 2026-11-12T16:00Z |  |
| [G9-X1](tasks/G9-X1.md) | E9-7: a reading model for BEN from recorded boards | pool |  | open | high | 2026-11-13T12:00Z |  |
| [G9-B4](tasks/G9-B4.md) | Card to profile distance and system detection | bill |  | open | medium | 2026-11-13T10:00Z |  |
| [G9-B6](tasks/G9-B6.md) | Three real cards read into the IR, each with its check sheet | bill |  | open | medium | 2026-11-13T18:00Z |  |
| [G9-D3](tasks/G9-D3.md) | Rating table fitted to the published Gen 5 to Gen 7 feeds | dave |  | open | medium | 2026-11-13T06:00Z |  |
| [G9-D5](tasks/G9-D5.md) | Experience store: per-board deltas, merge, epoch snapshot | dave |  | open | medium | 2026-11-13T12:00Z |  |
| [G9-S5](tasks/G9-S5.md) | Honesty and play-factor estimators; learning curve by boards seen | sam |  | open | medium | 2026-11-13T12:00Z |  |
| [G9-S6](tasks/G9-S6.md) | The house bots' own carding, measured | sam |  | open | medium | 2026-11-13T16:00Z |  |
| [G9-W3](tasks/G9-W3.md) | One command to prepare an environment and run the Gen 9 tests | will |  | open | medium | 2026-11-12T20:00Z |  |
| [G9-W4](tasks/G9-W4.md) | Queue metrics: are there too few thinkers or too few executors | will |  | open | medium | 2026-11-13T12:00Z |  |
| [G9-W6](tasks/G9-W6.md) | Script for the base swap | will |  | open | medium | 2026-11-12T22:00Z |  |
| [G9-B5](tasks/G9-B5.md) | Scorer trained with dropped calls; handing misread calls to the rules | bill |  | open | low | 2026-11-13T18:00Z |  |
| [G9-D6](tasks/G9-D6.md) | A small arena on a box with synthetic players | dave |  | open | low | 2026-11-13T18:00Z |  |
| [G9-A1](tasks/G9-A1.md) | Architecture v0 and work plan | g9 |  | resolved | high | 2026-11-12T08:00Z | accepted |

## Experiments

| Id | Title | Owner | Holder | State | Priority | Due | Note |
| --- | --- | --- | --- | --- | --- | --- | --- |
| [E9-0](experiments/E9-0.md) | What a nat of reading is worth: IMPs against log weight of the true layout | g9 |  | open | high | 2026-11-13T06:00Z |  |
| [E9-1](experiments/E9-1.md) | What the rule filter recovers on systems the scorer never saw | bill |  | open | high | 2026-11-13T02:00Z |  |
| [E9-3](experiments/E9-3.md) | How often spot cards nine and below are not equivalent | sam |  | open | high | 2026-11-12T20:00Z |  |
| [E9-4](experiments/E9-4.md) | Reading gain against carding bots, by honesty and scheme | sam |  | open | high | 2026-11-13T04:00Z |  |
| [E9-5](experiments/E9-5.md) | Arena simulator: schedule and promotion rule against fixed pairs | dave |  | open | high | 2026-11-13T02:00Z |  |
| [E9-6](experiments/E9-6.md) | What agreed signals are worth to the house pair | sam |  | open | high | 2026-11-13T10:00Z |  |
| [E9-7](experiments/E9-7.md) | A reading model for BEN from recorded boards | pool |  | open | high | 2026-11-13T12:00Z |  |
| [E9-2](experiments/E9-2.md) | Boards needed to identify a system from finished boards | bill |  | open | medium | 2026-11-13T10:00Z |  |

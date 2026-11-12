# Gen 9 work plan

> Written 12 November 2026 by the Gen 9 session (g9). The live state of every task and
> experiment is on branch `team/gen9` (`STATUS.md`, `tasks/`, `experiments/`); this page is the
> plan they come from and is updated at each checkpoint.

## Who does what

| Who | Area | Designs | Builds |
| --- | --- | --- | --- |
| g9 | Architecture | [Overall flow](architecture.md); the player model and the table contract (I3); the mixture over profiles (4.1); the experience schema (I6); rating and promotion statistics; release gates | The Gen 9 player shell that the readers plug into; reviews; merges into `feature/gen9` |
| bill | Bidding systems | Card IR for bidding, card to rules, the rule filter, card to profile matching, system detection | Rule filter, matching and detection, scorer training with dropped calls |
| sam | Signals and card-play reading | Carding rules as executable signals, the class rule, honesty estimation, per-player play factor | Carding bots (synthetic opponents), signal model, play reader, estimators |
| dave | Dynamic arena | Registry, epochs, schedule, admission, promotion, retirement, record and dashboard changes | Arena simulator, rating table from existing feeds, registry and epoch runner, experience store |
| will | Workflow and infrastructure | Work queue and experiment registry, executor briefing, queue metrics | `workq` tool, test runner for `feature/gen9`, box job queue, the base swap when Gen 8 lands |

The pieces that tie areas together are designed by g9: the player model, the reader calculus
and where it enters the engine, the experience schema, and the statistics that decide
promotion. Each lead designs inside its area against those interfaces and submits a short
design note before building.

## Checkpoints (UTC)

| When | What is due | What g9 does |
| --- | --- | --- |
| Thu 12 Nov, 12:00 | A design note per area (`docs/gen9/<area>.md` on the lead's branch) | Reviews the same afternoon; leads start their first module without waiting |
| Fri 13 Nov, 02:00 | First measurements: the filter's reading gain (E9-1), spot equivalence and the signal reading gain against carding bots (E9-3, E9-4), the arena simulator's error rates (E9-5), `workq` in use | Adjusts the plan; decides what goes into the review |
| Fri 13 Nov, 18:00 | Results frozen; branches merged or named | Assembles the review package |
| Sat 14 Nov, 01:00 | Review package to Max | |

## Tasks

Ids as on `team/gen9`. "Needs a box" marks work that cannot run in a session's own sandbox.

### Architecture (g9)

| Id | What | Due |
| --- | --- | --- |
| G9-A1 | Architecture v0 and this plan | done |
| G9-A2 | `PlayerModel`, `meet(table)` and the `experience-v1` schema as code and a schema file | Thu 12:00 |
| G9-A3 | Gen 9 player shell: Gen 8 player with reader hooks and the mixture over profiles; plays as its base when given nothing (tested) | Thu 18:00 |
| G9-A4 | Rating, field score and promotion test: the statistics, written so dave can implement and simulate them | Thu 14:00 |
| G9-A5 | Base swap: replace the Gen 8 snapshot with Gen 8's source once it is on main | when Gen 8 lands |
| G9-A6 | Review package | Sat 01:00 |

### Bidding systems (bill)

| Id | What | Due |
| --- | --- | --- |
| G9-B1 | Design note: card IR fields for bidding, compile to rule-bidder settings, filter semantics | Thu 12:00 |
| G9-B2 | Rule filter with `FitScorer`'s interface, evaluated on hand types | Thu 17:00 |
| G9-B3 | E9-1: what the filter recovers on auctions bid with systems the scorer never saw (true-layout weight; then IMPs, needs a box) | Fri 02:00 |
| G9-B4 | Card to profile distance, and system detection from finished boards (E9-2: boards needed to identify a system) | Fri 10:00 |
| G9-B5 | Scorer trained with dropped calls, and handing misread calls to the rules | Fri 18:00, stretch |
| G9-B6 | Three real cards read into the IR with their check sheets | Fri 18:00 |

### Signals and card-play reading (sam)

| Id | What | Due |
| --- | --- | --- |
| G9-S1 | Design note: situations, what each signal says, class rule, carding bots, estimators | Thu 12:00 |
| G9-S2 | Signal model and carding bots (declared carding, set honesty) | Thu 18:00 |
| G9-S3 | E9-3: how often spots nine and below are not equivalent, on recorded boards | Thu 20:00 |
| G9-S4 | E9-4: reading gain against carding bots by honesty and scheme (true-layout weight; then IMPs, needs a box) | Fri 04:00 |
| G9-S5 | Honesty and play-factor estimators writing experience deltas; learning curve by boards seen | Fri 12:00 |
| G9-S6 | The house bots' own carding, measured (their carding card) | Fri 16:00 |

### Dynamic arena (dave)

| Id | What | Due |
| --- | --- | --- |
| G9-D1 | Design note: registry, epochs, schedule, records, what collectors do, migration from today's plans and feeds | Thu 12:00 |
| G9-D2 | E9-5: arena simulator; schedule and promotion rule against today's fixed pairs (boards to a decision, error rates) | Fri 02:00 |
| G9-D3 | Rating table fitted to the published Gen 5 to Gen 7 feeds; does it reproduce the pair results | Fri 06:00 |
| G9-D4 | Registry, epoch manifest and a one-machine epoch runner; a player joins and one leaves between epochs | Fri 14:00 |
| G9-D5 | Experience store: per-board deltas, merge, epoch snapshot | Fri 12:00 |
| G9-D6 | A small arena on a box with synthetic players (needs a box) | Fri 18:00, stretch |

### Workflow and infrastructure (will)

| Id | What | Due |
| --- | --- | --- |
| G9-W1 | Design note: work queue and experiment registry beyond Gen 9, executor briefing, metrics | Thu 12:00 |
| G9-W2 | `tools/workq.py` on `team/gen9`: new, lease, renew, submit, resolve, release; tested against a local repository | Thu 16:00 |
| G9-W3 | One command that prepares an environment and runs the tests for `feature/gen9`, with honest skips | Thu 20:00 |
| G9-W4 | Queue metrics from the channel's history: waits, lease lengths, review delays | Fri 12:00 |
| G9-W5 | Box job queue and results convention for Gen 9 experiments | when a box is assigned |
| G9-W6 | Script for the base swap (G9-A5) | Thu 22:00 |

## How many thinkers and how many executors

Max asked. These are starting numbers with the measurements that will correct them; the queue
data from this week (G9-W4) goes into the review.

**Thinkers.** One architect and one lead per area that has its own body of context. For Gen 9
that is 1 + 4 as assigned, beside the existing Gen 8, operator, dashboard and training sessions,
which already act as leads for the engine, the fleet, the dashboard and the nets. Once the
arena is a standing population the areas are: reading (calls and cards; two leads while both
are being built, one later), the play engine, training, arena operations (with the workflow
tools once they exist), and evaluation. Evaluation should be its own lead: whoever decides
promotions should not be whoever submits candidates. That is one architect and five or six
leads. The limit on leads is the architect's review time: with file-based messages a review
costs roughly 15 to 30 minutes a lead a checkpoint, so six leads at three checkpoints a day
fit and a dozen would need a second tier.

**Executors.** A task suits an executor when it is self-contained: a pinned base commit, an
interface, a done-when, a time box of one to four hours. Three things cap how many are useful
at once: tasks that are ready (about two per area in this plan), boxes for experiments that
play boards (six exist; a 2,000-board match is about an hour and a half of one box at Gen 8's
fork-free rate of about 1,270 boards an hour), and each lead's capacity to review (two or three
submissions per half day beside its own work). That gives one or two executors per lead now,
four to eight in all, started by the lead for a specific task and ended with it.

**What would change the numbers** (each is read off the task files' history):

- Pool tasks open and unleased for more than an hour: add executors.
- Submitted work unreviewed for more than two hours: the lead or the architect is the
  bottleneck; add a lead or split an area.
- Leases expiring unfinished: tasks are too big; that is a decomposition problem, not a
  shortage of executors.
- Boxes idle while experiment tasks wait: add executors. Boxes full: more executors add nothing
  until compute does.

## Resources

Gen 9 holds no Azure box yet. Allocation is on `box/coordination`. Max's instruction of
12 November: g9 coordinates with the Gen 8 session, takes over its boxes when Gen 8 launches,
and may take one box before that if needed. The first experiments that need one are E9-1 and
E9-4 (expected from about 14:00 UTC on Thursday).

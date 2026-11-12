# Gen 9 architecture, v0

> **Design in progress, written 12 November 2026 by the Gen 9 session (g9). Nothing here is
> adopted.** No arena bot, plan or runtime uses it. It fixes the overall flow and the interfaces
> between the four work areas so that they can be built in parallel; the area leads' design
> notes (this folder) fill in each part and may change it. Numbers quoted from Gen 7 and Gen 8
> work name their source; everything else is a proposal to be measured.
>
> **Revised 12 November, 07:40 UTC**, after the four area design notes and the first measurements:
> section 4.2 (the card is a profile of its own, not a factor on every profile), 4.3 (the signal part is
> not tempered), section 6 and 7 (who bid is told apart from who plays; promotion test), section 8 (what
> perfect reading is worth). Area notes: [bidding](bidding.md), [signals](signals.md), [arena](arena.md),
> [arena statistics](arena-statistics.md), [workflow](workflow.md).

## 1. What Gen 9 is for

Gen 8 lets a bot be told what the other side has declared (a registered bidding system) and
which type of opponent it faces (a factor per bot id on how much to believe their plays).
Gen 9 turns that into a model of each player that is built when the player arrives, used at
every decision, and improved by every board played against them; and it turns the arena from
fixed generation-against-generation matches into a population that players join and leave.

| Asked for | Gen 9 component | Section |
| --- | --- | --- |
| A player arrives with a convention card and is mapped to profiles | Card reader, card IR, profile matching | 3 |
| No profile fits: the card becomes a rule-based scorer, or a filter on a scorer net | Rule filter compiled from the card | 4.2 |
| Even when a profile fits, the card filters the net | The same filter, always on | 4.2 |
| Read opponents' signals, including how often they are honest | Signal model with a learned honesty rate | 4.3 |
| An experience base per player that sharpens play inference | Experience store, per-player calibration | 5 |
| Players come and go; possibly the last fixed generation | Registry, epochs, scheduler, ratings, promotion | 6 |
| Task lists checked in and out, experiments that come and go | Work queue and experiment registry | [workplan](workplan.md) |

It implements, for the first time in code, sections 6, 7 and 15 of the prospectus
(`docs/Single_Dummy_Machine_v4.pdf`): opponent actions as evidence, opponent type as a latent
variable carried jointly with the layout, and a population with an archive, a training league
and an evaluation panel.

## 2. The player model

A **player** is a partnership that sits down in the arena: a house bot, a frozen anchor, an
outside bot, a synthetic opponent built for training, or a guest. What we believe about a
player has three layers, from general to specific. Every reading of that player's calls and
cards uses all three.

| Layer | What it is | Where it comes from | Changes |
| --- | --- | --- | --- |
| **Profile** | A known way of bidding and carding with trained experts: a row of the system-aware scorer (Gen 8 `SystemFitScorer`), a reading of the policy net. A player has a probability over profiles, `unknown` included | Matching the card to profiles; then the player's own boards | Per epoch |
| **Card** | What the player declared, as data: structured fields plus rules that say what each call and each signal means | Read from the convention card (ACBL, WBF, USBF summary form, notes) | When the player changes it |
| **Experience** | Sufficient statistics of what this player actually did on finished boards: how often calls break the card and in which direction, how often each kind of signal is honest, how predictable their card play is under our net | The arena's records | Per epoch |

The profile and the card are public agreements. Experience is our own notebook. None of them
ever contains anything about the board being played: experience is a snapshot taken at an
epoch boundary (section 6), so a board can be replayed exactly and a deal played at one table
cannot leak to the other.

Identity. A bot player is identified by its bundle (source, nets, settings: the arena's
existing actor identity) plus its declaration. A changed bot is a new player, as today.

## 3. Arrival: from a card to a seat in the arena

```
convention card ──reader──▶ card IR ──compile──▶ rules (what each call / signal means)
                               │
                               ├──match──▶ probability over profiles   (distance below)
                               │
past boards, if supplied ──────┴──▶ initial experience and a sharper profile probability
                                              │
                                   player package, status `candidate`
                                              │
                         admission boards (section 6) ──▶ `active`, with a rating
```

**Card IR.** One JSON document per card (`configs/cards/<id>.json`, schema `card-ir-v1`):

- `descriptor`: flat `field: value` pairs from a controlled list (`configs/cards/_fields.json`),
  for example `open.1nt.range: [15, 17]`, `open.major.length: 5`, `open.1c: strong16`,
  `open.2d: weak`, `resp.2over1: gf`. Carding fields are Gen 8's
  `configs/systems/_carding_fields.json`. This is what a net can be conditioned on and what
  profile matching compares.
- `rules`: what executes. In v1, settings for the project's own rule bidder
  (`bridge_harness/rule_bidder.py`: a `Settings` dictionary; every call has a meaning with
  point and length ranges), so any card inside that family runs today. A declarative list of
  meanings for cards outside the family is the next step and has the same interface.
- `provenance`: source format and file, who or what read it, confidence per field, and the
  text the reader could not place.

Reading a free-form card (a PDF or a page of notes) into the IR is a job for an agent with a
schema, a validator and a round trip that a person can check: the reader also produces what the
card would open and respond on a fixed set of hands, and those are shown beside the card.

**Matching a card to profiles.** The distance from a card to a profile is the rate at which
the profile's own bidder breaks the card's rules: bid a fixed set of deals with the profile's
generator, and count the calls that the card's meaning for that call does not allow, among the
calls the card covers. It is executable for neural and rule bidders alike, it weights each
agreement by how often it comes up, and it needs no hand-set field weights. The profile
probability starts from those distances and is then updated from the player's own finished
boards by the likelihood of their calls under each profile's scorer (system detection, deferred
from Gen 8). A card far from every profile leaves most of the weight on `unknown`, and the rule
filter does the work.

## 4. At the table: reading calls and cards

The engine already weights every candidate layout `x` of the hidden hands (Gen 6
`type_log_weights`, Gen 7 `play_log_likelihood`):

```
log w(x) = log prior(x)
         + sum over hidden seats s of        S(hand_x(s) | calls of s)          hand-fit scorer
         + alpha * sum over hidden plays i of log P_net(card_i | view_i(x))      policy net, floored
```

Gen 8 made `S` depend on the declared system of the side that called and added a factor per
opponent type on the last term. Gen 9 keeps this form and makes both terms depend on the player
model `M` of the partnership that acted.

### 4.1 Calls: a mixture over profiles, carried through the whole board

For a partnership `P` with profile probabilities `pi_P(k)`:

```
auction weight of x for P  =  sum over k of  pi_P(k) * product over P's seats s of exp(S_k(hand(s)))
```

- The sum over profiles is outside the product over seats and calls: a pair plays one system
  for the whole board (prospectus section 7; the Gen 8 guide also asks for mixing scores and
  not tables). In code this is a log-sum-exp over profiles of the summed seat scores, in a
  `type_log_weights` that Gen 9's player overrides.
- `P`'s visible hands count too. When dummy belongs to `P`, dummy's fit under each profile
  multiplies `pi_P(k)` before the hidden hand is weighted: seeing dummy tells us which system
  they are playing.
- In normal play only one side's system is uncertain (we know our own), so this costs one
  scorer pass per candidate profile. With at most four candidates kept, that is small next to
  the solver.

### 4.2 The card: a profile of its own, and a correction to the others

The card compiles into rules: in each situation the card covers, an ordered list of calls with
the hands that make them ([bidding note](bidding.md); 81 fields, five systems compile today:
2/1, SAYC, Acol, Precision, Polish Club). From the rules, the likelihood of a call for any hand:

```
P(call | hand) = (1 - eps) * [the first rule the hand satisfies is this call] + eps * (a soft share by how far the hand is from each rule)
F(hand | calls of s) = sum over the seat's calls that the card covers of log P(call | hand)
```

`eps` is the player's measured rate of off-card calls, per family of calls (section 5). The
ordered rules give negative inference (a pass denies an opening); a hand one point outside a
range costs less than a hand five points outside.

**First measurement (bill, 12 November; one seat's true hand over a uniform pool, nats):**

| Auctions bid by | Hand-fit scorer `S` | Card `F` | `S + F` |
| --- | ---: | ---: | ---: |
| House Gen 5 bidder (read with an approximate 2/1 card) | 2.18 | 0.85 | 1.77 |
| 2/1 card / SAYC card | 0.61 / 0.75 | 1.68 / 1.67 | 0.97 / 1.08 |
| Acol card / Polish Club card | -1.34 / -1.16 | 1.65 / 1.43 | -0.55 / -0.72 |
| Precision card | -2.49 | 1.42 | -1.90 |

Two things follow, and they change the first version of this section:

- **On a system it was not trained on, the house scorer is worse than not reading the auction
  at all** (negative gains), and multiplying the card onto it does not rescue it. So the card
  is not a factor on every profile. It is **a profile of its own** in the mixture of 4.1,
  reserved id `card`: its row is `F` alone, with no scorer. A foreign system declared with a
  card is read by its rules; the house scorer keeps only the weight that matching (section 3)
  and the player's own boards give it.
- **On the house system an approximate card costs weight** (2.18 falls to 1.77). So on a net
  profile `k` the card's term is applied only on that profile's **residual**: the situations
  where profile `k`'s own bidder breaks the card more often than a threshold, which is where
  this player's card really departs from the profile (a 14 to 16 no-trump under a 15 to 17
  profile). That is "even when they match a profile their card filters the net", without
  paying for the card's approximations elsewhere.

Still to come: handing single calls to the rules (a scorer trained with calls dropped), and
experiment E9-8, which asks whether replaying a known bidder on each candidate hand reads the
house auctions better than the scorer does. If it does, every profile whose bidder we hold
(house nets, BEN's own bidder, rule bidders, compiled cards) is read by replay on the pool, the
scorer only draws the pool, and the mixture compares like with like.

### 4.3 Cards: the net for the choice that matters, the carding rules for the spot

A defender's card says two things: what they chose to do (win, duck, switch, which suit to
discard), and which of several cards that do the same thing they picked to say something to
partner. The policy net is trained on the house bots, whose spot-card habits are their own. For
a player with declared carding the reading is split:

```
log P(card | view, x) = phi_P * log P_net(class of the card | view)       what they chose to do
                      + log P_signal(card | class, hand, situation; carding of P, h_P)
```

- **Class.** The spot cards (nine and below) of the suit played form one class; an honour is
  its own class; on the opening lead the class is the whole suit led. Measured on 21,057
  defender decisions (E9-3): the spots of a class differ in tricks on the true deal 1.49% of
  the time, and almost never (0.10%) where the search itself rates them equal, so a carding bot
  signals only among cards its search ties.
- **Situation.** From public information: opening lead, following to partner's lead, following
  to declarer's lead, first discard, giving a ruff. The player's carding descriptor says which
  signal applies there (attitude, count, suit preference, none) and which way round.
- **Signal probability.** With honesty `h`: the prescribed spot with probability
  `h + (1 - h) / n`, any other of the `n` spots with `(1 - h) / n`. What the signal says is a
  fact about the hidden hand (parity of the suit for count, an honour in the suit for attitude,
  where the side strength is for suit preference, length for a fourth-best or third-and-fifth
  lead), so this is a likelihood over layouts like any other term.
- **Honesty is per player and per kind of signal**, learned from finished boards (section 5),
  starting from the profile's value. `h = 0` makes the spot say nothing; nothing is ever ruled
  out.
- **`phi_P`** is Gen 8's opponent factor, learned per player instead of set by hand. Gen 8's
  calibration found the best factor to be 1.0 for the house bots, 0.2 to 0.5 for Gen 1 and the
  fixed-carding types, and used 0.3 for an unknown opponent (`configs/gen8-proto-bots.json`,
  bot `8x-32`).
- **Not tempered.** The net's part keeps the exponent Gen 7 and Gen 8 fitted for it; the signal
  part is a likelihood and is applied in full.
- **House bots** keep the net's own reading of spots (their habits are in the net). Measuring
  those habits with the same tools gives the house bots' own carding card, which other players
  are owed (disclosure).

### 4.4 What the bot does with it

Layout weights feed the same search as Gen 8 (weighted layouts, solver, tree). Gen 9 v1 changes
what the bot believes, not how it searches. The bot's own bidding and carding stay the house
ones. Playing a guest's card as their partner uses the same compiled rules as a bidder and is
left for after v1.

## 5. After the board: experience

Every finished board updates the notebook of each player seen. All hands are known then, so
every statistic is exact.

| Statistic | Updated from | Used for |
| --- | --- | --- |
| Profile probability | Likelihood of the pair's calls on their actual hands under each profile | 4.1 |
| Off-card rate `eps`, and where the ends of each declared range really are | Each covered call: did the hand fit the card's meaning, and by how much not | 4.2 |
| Honesty `h` per kind of signal | Each signalling chance with two or more spots: was the prescribed spot played | 4.3 |
| Play factor `phi`, floor | Gain in the true layout's weight at a grid of factors (Gen 8's play-information measure, per player) | 4.3 |
| Error profile | Tricks given up against the solver by role and trick | Opponent replies in the tree (later) |

Updates are sums keyed by board, so collectors on different machines add theirs in any order
and a board counted twice is detected. A snapshot of the store is frozen at each epoch boundary
and named in every record played under it. Schema `experience-v1`; the shrinkage toward the
profile's values is part of the schema, so a player with ten boards is read almost as their
profile and one with a thousand as themselves.

A learned per-player vector fed to the policy net (fitted from the same boards) is the step
after these statistics. It is not in v1; the statistics come first because each is one or two
numbers that a few dozen boards can estimate.

## 6. The arena as a population

| Piece | What it is |
| --- | --- |
| **Registry** | One player package per player: bundle identity, declaration (system package or card), kind (house, anchor, synthetic, outside bot, guest), status (`candidate`, `active`, `anchor`, `retired`) |
| **Epoch** | A frozen roster, schedule weights, experience snapshot and deal source, for a set number of boards or hours. Players join and leave, and weights change, only between epochs. Collectors read the current epoch's manifest from a branch and need no other instruction |
| **Schedule** | Shares per purpose (training self-play, pending promotion tests, evaluation panel, admissions), then within a purpose the pairs whose results can still change a decision |
| **Rating** | A Gaussian model of paired-board IMP differences, `d = s_i - s_j + noise`, with anchors fixing the scale; a pair's own mean replaces the model's where there are enough boards. A player's headline number is its **field score**: expected IMPs a board against a declared mix of opponents, with the worst cell shown beside it |
| **Admission** | A new player gets a small share against the champion and the anchors until its rating is known to a set width |
| **Promotion** | A candidate replaces the champion when a sequential test of the direct match that is valid at every look shows a lead, and no panel cell shows a regression beyond a set tolerance ([statistics](arena-statistics.md), section 3). This is the rule Max set by hand for 7.1 against 7.0 (at least 1,000 boards and a 95% lead), made safe against repeated looks |
| **Retirement** | A player leaves the active roster when it no longer informs a decision or adds to training variety; its package, records and rating stay |

Synthetic players (the rule bidder with sampled settings, carding rules with set honesty, older
nets, weaker searches) are admitted like any other and are what Gen 9's readers are trained and
tested on, since their systems, signals and honesty are known exactly.

"The last fixed generation" then means: after Gen 9 the champion changes by promotion inside
the arena, and a generation number is a label put on a champion afterwards.

## 7. Interfaces between the areas

| # | Interface | Form | Owner | Used by |
| --- | --- | --- | --- | --- |
| I1 | Player package | `configs/players/<id>.json`, schema `player-package-v1`: bundle, declaration, lineage (what each net trained on), needs. Immutable; a player's status is the fold of events in an append-only registry log ([arena design](arena.md)) | dave | all |
| I2 | Card IR | `configs/cards/<id>.json`, schema `card-ir-v1`; field list `configs/cards/_fields.json` | bill (bidding fields, rules), sam (carding fields, rules) | readers, matching |
| I3 | Player model at the table | [`bridge_harness/player_model.py`](../../bridge_harness/player_model.py): `PlayerModel(id, kind, profiles, bidding, carding, experience)`, read-only. Two facts reach a player. Who plays the cards against it: the runner's existing `meet(opponent)`, once a board, with a `PlayerModel` or a bot id resolved against the models in the player's own spec. Who made the calls at this table: `auction_by(bidders)`, before each table, four models or ids in seat order; without it each side is taken to have bid for itself. In a common auction the bidding layer read for both sides is the common bidder's, while carding and play experience stay the card player's | g9 | bill, sam, dave |
| I4 | Bidding reader | An object with `type_log_weights(o, view, length, hon)` (4.1 and 4.2); the rule filter alone has `FitScorer`'s `type_log_score` | bill | engine |
| I5 | Play reader | An object with `play_log_likelihood(o, view, assign, plays)` (4.3) | sam | engine |
| I6 | Experience | [`bridge_harness/experience.py`](../../bridge_harness/experience.py), `experience-v1`: four additive kinds of statistic (`count`, `hist`, `moment`, `loglik`), per-board deltas keyed by board, a merged store, a frozen snapshot, and estimators that shrink toward a prior. Names: `bid.<family>`, `profile` (bill); `card.<signal>`, `play.<what>` (sam) | g9 (schema and algebra), bill and sam (their statistics), dave (storage, merge across collectors, snapshots) | readers |
| I7 | Epoch manifest, result record, rating table | `epoch-v1` on a control branch; in the first phase the epoch, player and snapshot ids ride in each cohort's run manifest, so records and the collector runtime are unchanged; `ratings-v1`, one table per bidding condition ([statistics](arena-statistics.md)) | dave | collectors, dashboard |
| I8 | Task and experiment files | `team/gen9` branch, README there | will | everyone |

Rules that hold across all of them:

- Nothing reaches a player's decision except its `Observation` and the table's `PlayerModel`s.
  Hidden hands are labels for training, experience and scoring only.
- Every new input is inert by default: a Gen 9 player given no card, no profile probability and
  an empty experience plays exactly as the Gen 8 base it is built on, and a test says so.
- Each reader term can be switched off by itself, so each has its own measured effect.

## 8. How it is judged (proposed gates, for Max)

1. **Leverage.** Gen 8's measure is kept. Gen 9 adds experience leverage: against an unfamiliar
   player type, results on fresh boards with a snapshot of N boards of experience beat results
   with none, and the gain grows with N.
2. **Mixed populations.** For a system and a carding scheme the bot has never trained on, given
   only the card: the readers recover a stated share of the gap between a generic reading and a
   reading by an expert trained on that type (in the true layout's weight, and in IMPs), and
   nothing is lost against the house bots.
3. **Strength.** Higher field score than Gen 8, with no anchor cell worse by more than a set
   tolerance.
4. **The arena runs itself.** A player is admitted from a card with no code change; the rating
   table reproduces the fixed-pair results of Gen 7 and Gen 8 within their intervals; a
   promotion is decided by the rule with no hand-written instruction to collectors.

**What reading can be worth at most.** A test-only bot that is told the deal and otherwise is the
Gen 8 prototype beats that prototype by +2.36 +- 0.61 IMPs a board (39 boards, 12 November; 20
won, none lost). That is the whole prize for reading hidden cards better within this search;
Gen 8's reading of the play from trick 1 took about 0.4 of it. Experiment E9-0 measures the
curve in between (IMPs against nats of the true layout's weight), which turns every reader's
offline gain into an expected gain at the table.

The comparison used throughout is the prospectus's: generic reading, fixed mixture, inferred
model, and an oracle told the true type. The oracle gap says what a perfect player model would
be worth before it is built.

## 9. Not in v1

- Our own bidding changing with the opponents' system (defences to a strong club and the like).
- Playing a guest's system as their partner.
- Choosing when our own signals should be honest.
- A learned per-player vector in the policy net.
- Human guests at a table. The card path is built so that a person's card works, and it is
  tested on bots.

## 10. Open questions

- How much of an outside system can the rule bidder family express, and what is the smallest
  declarative rule language that covers the rest.
- Whether spot cards nine and below are equivalent often enough for the class rule in 4.3.
- Whether honesty should depend on the situation (honest when partner needs it) from the start.
- Whether ratings need a term for pairs that beat each other out of order (style match-ups).
- What the field mix is: which opponents, in which shares, define "strength" from now on.

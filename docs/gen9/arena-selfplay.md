# Gen 9: a diverse arena as the source of self-play training (design note, G9-A8)

> **Design in progress, g9, 13 November 2026. Nothing here is adopted.** For Max's Friday-evening review
> (Sat 14 Nov 01:00 UTC). It builds on [the arena design](arena.md) (dave, G9-D1: packages, registry, epochs,
> schedule, admission, promotion, retirement), [the arena statistics](arena-statistics.md) (G9-A4, revised after
> E9-5: ratings, tests, where boards go) and [the results data](arena-results.md) (G9-D8), and changes them only
> where it says so. Max, 13 Nov 01:16 UTC: "deeply and broadly address all the issues around managing a highly
> diverse arena, which will become increasingly important as self play training becomes a bigger slice of our bot's
> capabilities."
>
> Each number names its source. "Not measured" means no one has measured it.

## Summary

1. Arena boards are training data. Rollout net v2 learned from every bot's decisions in the house feeds (Gen 5RZ to Gen 8),
   with the bots' identities as an input. The arena's schedule therefore decides what the nets learn as well as what
   the ratings measure.
2. Self-play's known failure modes all have a bridge form. Three show in our numbers already: the net depends on
   knowing who is playing; a carding policy's worth depends on who reads it; and what our cards tell a reader (0.124
   tricks a board) costs nothing against opponents who do not read.
3. The population gets roles (section 2): champion, past champions, league, synthetic styles, outside panel, held-out
   styles, exploiters and guests, each with a purpose, a share, and rules for entry and exit. The structure follows
   the AlphaStar league.
4. Diversity is measured three ways (declared, behaviour, results). A member that adds nothing on any of them retires
   (section 3).
5. Training opponents are chosen by what the champion still has to learn from them, with floors so that no kind of
   opponent drops out of the training data (section 4).
6. Ratings stay in IMPs a board, with three additions (section 5): the headline field is declared rather than
   "everyone equally"; a score that ignores redundant members is shown beside it; and a variance reduction for the
   large swings is tested.
7. Each champion version gets an exploitability report: what an informed reader of its cards gains, what a deceiver
   gains against its reader, and later what a bidding exploiter gains (section 6). The same measurement catches
   understandings that self-play partners learn without declaring them.
8. A newcomer gets a "who" for the nets from Gen 9's arrival mixture instead of the generic row (section 7).
9. Decisions for Max: section 10. Tasks: section 11.

## 1. What self-play changes

### 1.1 Arena boards are the nets' training data

Rollout net v2 (plan, board 13 Nov 06:47 UTC) was trained on 30.4 million decisions from 75,390 deals: v4.1's feeds and
every Gen 7, 7.1, 8 and Gen 5RZ feed (Gen 6 is the largest share of its rows), every bot's decisions, 18 bots by id, with the deciding side's bot and the other side's bot
as an input (`net.who`). So the arena already sets the training distribution. Today it does so by accident: the feeds
hold whichever pairs each generation's plan scheduled for its ratings.

### 1.2 The failure modes, in bridge form

| Failure mode | Bridge form | Measured? |
| --- | --- | --- |
| Agents trained by self-play or population play "overfit to their training partners" (Strouse et al. 2021) | The net reads a bot it knows through that bot's row, and any other bot through a generic row | Yes: with the ids blank, v2's log-loss on held-out decisions rises from 0.525 to 0.627 (plan, 06:47) |
| A policy's worth depends on the opponents | Designed signals gain the defence +0.06 tricks a board against `8p-32`, which misreads them, and -0.01 against a declarer told the scheme (E9-6 bench, commit 306c16b). Bidding style (light preempts, say) should behave the same way | Signals: yes. Bidding style: not measured |
| What a policy gives away costs nothing against opponents who do not take it | Our card play is worth 0.124 +- 0.026 tricks a board to a reader of our strength (E9-16). House bots read none of it, so self-play among them never charges for it | Yes |
| Strategy cycles and forgetting (AlphaStar's agent "chasing its tail") | A champion that beats the previous champion and loses to an older style | Not seen in our feeds; the per-pair leave-one-out test (A4 after E9-5) is the detector |
| Conventions nobody declared | Partners trained together learn to read each other's habits (a tie-break preference, a lead style). In bridge that is a partnership understanding: the laws require it to be disclosed, and opponents can read it too | Not measured (section 6.3) |

## 2. The population: roles

| Role | Purpose | Today | Entry | Exit |
| --- | --- | --- | --- | --- |
| **Champion** | The bot we ship; the learner | `8s-32` (Gen 8 candidate) | Promotion test (A4 section 3) | Replaced; becomes a past champion |
| **Past champions** | Guard against forgetting; a series of our own earlier styles | Gen 1 to Gen 7.1 | Automatic on replacement | Protected while it is the last of its lineage |
| **League** | Variants that differ from the champion in one or two features (search width, net, tie-break, randomization) | `6-256`, `5RZ192`, `8c-32`, the variants merged on the ladder; `8x3-32` (8X v3), which Max put into the arena at 06:40 UTC; the Gen 9 candidate `9a-32` (cohort against `8s-32`, `71s-32`, `8p-32` and BEN 64) | Admission (A4 section 2) | Redundancy rule (section 3.3) |
| **Synthetic styles** | Known systems, styles and carding at set honesty: exact ground truth for readers, and the variety the house lineage lacks | The arrival run's guests (G9-D6) | Generated from the card descriptor (bill: systems and styles; sam: carding and honesty) | Redundancy rule; at least one per system family, carding scheme and honesty level is kept |
| **Outside panel** | Strength against bots we do not control; a drift check | BEN 16, BEN 64 | Max (licence, disclosure) | Max |
| **Held-out styles** | A generalization check: kept out of every net's training data | None yet | A synthetic style or panel member set aside | Released to training when replaced by a new held-out style |
| **Exploiters** | Find the champion's weaknesses (section 6) | None | Built against each champion version | Reset when the champion changes |
| **Guests** | Newcomers with a card (G9-B8 intake) | The arrival run's guests | Card intake, then admission | When they leave; records and experience stay |

AlphaStar (Vinyals et al. 2019) ran a league of main agents, main exploiters that play only the current main agents,
and league exploiters that look for weaknesses of the whole league, adding frozen copies of agents to the league as
training went on and resetting exploiters to keep them diverse. The bridge version differs in three ways. Our house
lineage already supplies the frozen copies. Synthetic styles are cheap and exactly known, which a game without
declared systems does not offer. And bridge requires systems and carding to be declared, so every member carries a
card (interface I2) and readers are judged against it.

## 3. Diversity

### 3.1 What can vary

| Axis | Values that exist or can be built now | Who builds them |
| --- | --- | --- |
| Bidding system | House lineages (`house-gen6`, `house-gen5`, `house-dds40k`), BEN's, Precision (`8c-32`'s rule bidder), the rule bidder's other system tables | bill |
| Bidding style | Preempt discipline by vulnerability, opening and overcall strength, from style statements (intake sample: `team/gen9:samples/notes/style-a.md`) | bill (G9-B8 style section) |
| Agreements by seat and vulnerability | A few for most pairs; whole systems change by seat and vulnerability for others (Max, 04:53) | bill (G9-B8 variants) |
| Carding | None, standard, upside-down, odd-even; count and attitude by situation | sam |
| Honesty | 1.0, 0.8, 0.5, and by situation (honest early, false cards in the trump suit) | sam |
| Card play engine | Search width, nets, rollout seats, claim finder | house, 8X |
| Reading | None, auction only, auction and cards, by class | g9, sam |
| Randomization | None, among exactly equal cards, among close choices | g9 (E9-16) |

The rated population today varies mainly along one axis, the card play engine. The house bots share one bidding
family and signal nothing (E9-9); `8c-32` is the only other system on the ladder. So the population that trains the
nets is narrow on exactly the axes Gen 9 reads.

### 3.2 How to measure it

Three distances between two members:
- **Declared**: the share of the card descriptor's 81 fields that differ, plus their style statements. Cheap; says
  what they claim.
- **Behaviour**: on a fixed set of stored decisions (p41's 21,417 house decisions, then the cohort's), the share
  where their top choices differ and, for members with a policy, the Jensen-Shannon divergence. Says what they do.
- **Results**: the distance between their rows of the cells matrix (A4 section 1), in standard errors. Says whether
  they matter to anyone's rating.

### 3.3 How much, and the redundancy rule

How much diversity training needs is not known for bridge. E9-18 (section 11) measures the first part of it on data
we already hold. Until then the rule only stops boards being wasted: a member is redundant when its results row is
within noise of another member's, its choices differ in double-dummy value from that member's on fewer than 5% of
paired decisions, and it declares the same card, each shown by an equivalence test (dave's review): the 90% interval
of the direct difference inside +-0.1 IMPs a board and the 90% interval of the value-changing share inside 5%. At a
board SD of 2.5 that takes about 1,700 direct boards when the difference is zero and about 3,900 for 80% power, so a
member is never retired for lack of data, and the rule seldom fires; the newer of the two retires unless protected. E9-20 (13 Nov,
`reports/gen9-arena-diversity-2026-11-13`): no current member is redundant. Results alone would pair `6-32` with
`8c-32`, and card play alone would pair `8c-32` with `8s-32`, which never chose differently in 25,953 paired card
decisions but bid differently and are 0.79 IMPs a board apart natively. The threshold counts value-changing choices
because randomizing among equal cards makes cards differ without changing anything. arena.md's
protections stand (anchors, the last member of each declared system and carding scheme, anything a person protects);
added: the last past champion of each lineage, and every held-out style.

## 4. Who plays whom

**Shares.** What runs today is the gain rule of the arrival run (`configs/arena9/rules-arrival.json`, A4 section 4 after
E9-5): training 10% (self-play), promotion 30%, and gain 60%, which sends boards to the contrasts whose variance falls
most (admission and the panel) in place of fixed panel and admission shares. arena.md's table (training 55%) was the
first design. This note starts from the gain rule. The two new purposes enter it as contrasts rather than fixed shares:
**exploitation probes** (champion against each exploiter) and **robustness** (champion against each held-out style)
get boards when their variance is the one that falls most. Training rises above 10% in steps as the nets consume
arena data (the SiD loop's rounds set that demand); each step is a rules version, so Max sees it.

Inside training:
1. **Self-play** (champion against champion): on-policy data. It counts nothing in ratings (A4).
2. **League and past champions**, weighted by what the champion still has to learn from them. AlphaStar's
   prioritized fictitious self-play weights each opponent by how often it beats the learner. The bridge version
   weights by how far the champion's cell against the opponent falls below what the two strengths predict, using the
   shrunk pair effect the ratings already compute (the cell minus the prediction, with t2) rather than the raw
   residual, so small pair effects (SD 0.08 today, 5.2) do not send boards after noise; times the pair's fork yield
   (decisions where the two tables part, which is where training rows come from). Floors as in item 3, and no
   opponent's weight more than doubles between epochs (arena.md section 4).
3. **Synthetic styles and guests**, with a floor per axis so that every system family, carding scheme and honesty
   level appears in each epoch's training data.

Default split of the training share until E9-18 reports: 50% self-play, 30% league and past champions, 20%
synthetic styles and guests. These are placeholders, not results.

**Condition by purpose.** Card play trains on both conditions, each table labelled by its `auction_source`
(`systems:NS|EW`): a common auction is bid by the house net at all four seats, so only native tables show the nets
another system's auction and the play that follows it. Common tables isolate the play for evaluation. Bidding and
auction reading need native tables.

## 5. Ratings in a diverse population

**5.1 Unit.** Ratings stay in IMPs a board (Max, 13 Nov 01:23). On E9-0's two 800-board box matches, boards of 10 or
more IMPs (5% of boards) carry 61% to 65% of the IMPs won and about 80% of the variance (common-auction box matches;
on the arena's native boards the share is 10% of boards and 76%, 5.4), and counting boards won and lost detects the
same edges with 1.5 to 1.9 times fewer boards. Won/lost is used as a fast screen; decisions stay on
IMPs.

**5.2 The field.** The provisional field score in `arena-results-v1` weights the rest of the population equally.
That fails in a diverse arena. Balduzzi et al. (2018) point out that adding copies of an agent that a player beats
raises that player's Elo-style rating; here, twenty synthetic variants of one style would make beating that style a large
part of "strength". Proposal: the headline number is the field score against a **declared field** (a decision for
Max, section 10). Beside it: the **Nash average** (each member's expected cell against the maximum-entropy
equilibrium of the cells matrix, which adding redundant members does not change; Balduzzi et al.) and the worst cell
(A4). E9-21 (13 Nov, `reports/gen9-arena-field-2026-11-13`): on today's 22 points the field moves the levels, not
the order (Spearman 0.999 between the two fields tried); the equilibrium is `8s-32` alone, so the Nash average is
each point's cell against the champion; and its standard errors are about the field scores'. The population is close
to transitive (pair-effect SD 0.08 IMPs a board), so the choice of field starts to matter once it is not. The Nash
average is shown beside the field score; decisions stay on the field score and the tests.

**5.3 Pairs out of line.** A diverse population should produce more pairs that one strength number does not explain
(style match-ups). The leave-one-out test per pair (A4 after E9-5) finds them, and the page shows the share of
between-pair variance the strengths explain. If that share is low, one number per member is not enough and the page
shows each member's cells by role.

**5.4 Variance.** The noise is in the large swings: on the 64,790 native boards below (arena feeds; E9-0's
common-auction matches give 5% and 80%, 5.1), boards of 10 IMPs or more are 10% of boards and 76% of the sum of squares. Each comes from a decision whose result turns on the layout: a contract
one table bid and the other did not (a slam on a finesse), or a line of play. Replacing the layout's luck in those
decisions by their expected value is the bridge form of AIVAT (Burch et al. 2018), which cut the standard deviation
of a poker match by 85%. For contracts, two versions:
- **cheap**: re-score each swing board by the double-dummy expectation of each table's contract over layouts
  consistent with its auction. Biased, since it replaces the play of those contracts by double dummy; useful as a
  screen if it removes much of the variance.
- **unbiased**: AIVAT's construction, which needs the posterior over layouts given the public auction and play under
  the players' known policies. The replay reader computes exactly that for our own bots, at a high cost in time.

A bound before any solving (E9-19 log, 13 Nov 07:30 UTC; 64,790 native boards of the 113 registered feeds, SD 4.35
IMPs): boards where the two tables' contracts differ are 12.8% of boards and 37.9% of the sum of squares (house pairs
9.6% and 30.2%; pairs with BEN 23.1% and 54.7%). The cheap version touches only those boards, so it can lower the SD
by at most 16% on house pairs and 33% on pairs with BEN. Most of the variance is card play in the same contract,
which only the play version can reach: a correction at the trick where the two tables' plays part, using the
bench's machinery (layouts and stored solves per decision). In common auctions (E9-0's matches) every swing is of
that kind.

Measured (E9-19, 13 Nov, `reports/gen9-e9-19-2026-11-13`). Today's house bots all bid with the same net, so the two
tables of the Gen 9 cohort, and of every pair among `8s-32`, `8x3-32` and `71s-32`, never reach different contracts:
those comparisons are card play only. Contracts differ only against an older generation or a foreign system. On
2,322 native boards of two Gen 8 feeds (439 with different contracts), the cheap version cut the SD of those boards by
29.6% (23% against `8c-32`, 38% against Gen 1 and Gen 5) and of all boards by 12%, but moved means by up to 1.7 IMPs a
board on the boards it touched, since double-dummy play replaces the pairs' real play there. It is not proposed as a
screen (the registered bar was 30%); the play version is the one that would matter for the cohort.

## 6. Exploiters, leakage and declared understandings

**6.1 An exploitability report per champion version**, on the bench (offline, in double-dummy tricks on stored
solves; E9-0 showed bench tricks predict played IMPs):
- **Informed reader**: a reader that knows the champion's card play policy exactly, reading its cards (E9-16's
  measurement). `8p-32`: 0.124 +- 0.026 tricks a board. Randomizing among exactly equal cards denies 0.01 to 0.04 of
  it at no played cost (`8r-32` against `8p-32` +0.014 +- 0.126 IMPs a board over 800 boards), so it is the default
  for new house versions. Frozen members keep their settings: the change gives a new identity, so a randomizing
  version is a new point or variant on the ladder, and the bots already in the arena are not changed. 8X v2 and v3 mix among equal cards by the net's probabilities (x8, commits 0bcdbc2
  and 1a779a9).
- **Deceiver**: a defender whose honesty is set by situation, playing against the champion's reader. What it gains
  is what trusting costs.
- **Bidding exploiter** (later): competitive bidding tuned against the champion's actions.

**6.2** Exploiters are rebuilt when the champion changes.

**6.3 Declared understandings.** When the champion partners itself, any regularity in its cards that its partner's
reader uses is a partnership understanding. Because `net.who` names our own bot in partner's seat, the nets can learn
such regularities from self-play data. Proposed measure: what the champion's reader gains from partner's cards with
partner's own id against the generic row, beyond what the declared card explains. A gain above noise is either
randomized away or written on our card. Not measured.

## 7. Newcomers and leavers

**7.1 Arrival.** Card intake (G9-B8), then profiles and `arrive()`; experience moves the profile probabilities
through `believed()` at each epoch boundary (architecture sections 3 and 5). The newcomer gets the admission share
until the standard error of its rating is 0.15 IMPs a board or it has 2,000 boards (A4 section 2).

**7.2 How fast a newcomer is learned.** Not measured as a curve. The arrival run's epochs (G9-D6) give a first one:
nats a call and IMPs a board against boards seen (E9-22).

**7.3 The nets' view of a newcomer.** Reading known bots through the generic row costs v2 about 0.10 in log-loss a
decision (section 1.2); for a bot it never saw, the cost is not measured. Gen 9 already holds a better prior for a
newcomer: the arrival mixture over profiles. Proposal: give the net the row of the profile the arrival mixture believes (or a mixture of rows), and
later a per-player embedding learned from experience (the brief's experience base per player). E9-22 tests the first
step on bots v2 never saw (the arrival run's guests), with a bot v2 knows, read with its own row and with the
generic row, as the control.

**7.4 Leavers.** Retired by rule (arena.md section 5) with the protections above. Packages, records and experience
stay, and a returning guest resumes from its experience.

## 8. The page

Now: the ladder at the top (strength against introduction date, bench priors, time per decision, a drill-down per
bot), the Gen 9 cohort's feed registered as generation 9 (about 07:03 UTC), and Gen 9 as the default view since 07:19
UTC (Max; Gen 8 at `?source=gen8&older=1`). `arena-results-v1`
(G9-D8) holds the data for one page per population and one per player.

Additions for a population (G9-D10):
- the cells matrix as a heat map ordered by strength, with pairs out of line marked;
- per member: declared card, role, status, what Gen 9 has learned about it (profiles, honesty, play factor), and its
  cells by role;
- per champion version: field score, Nash average, worst cell, the exploitability report, and the outside panel's
  cells over time;
- per epoch: where the boards went by purpose and role (the training mix).

## 9. People and compute

| Work | Who |
| --- | --- |
| Design, statistics, the experiments in section 11 | g9 |
| Arena operation: controller, epochs, registry, page data | dave; g7 runs today's arena boxes (azure1, azure3) |
| Synthetic systems and styles | bill |
| Carding, honesty, deceivers, the informed reader | sam |
| Box queue and infrastructure | will |
| Training runs for E9-18 and later training-mix runs | a training box (azure2 and azure5 are plan's and x8's); Max's decision |

Measured cost: the cohort plays about 200 boards an hour on azure4's seven workers (about 125 worker-seconds a
board, 32-world searches, with seven workers contending for memory and the solver cache; one process alone took 66 to
114 s a deal), and `9a-32` takes 0.354 s per card decision with a choice against `8p-32`'s 0.376 on the
same box (dave, 07:06 UTC), so the player model adds no time. A promotion test for a lead of 0.1 IMPs needs about
4,000 direct boards (A4). At this cost the training share is small; cheaper players (net-only play) would change
that, and their speed is not measured here.

## 10. Decisions for Max

1. **The field that defines strength**: which opponents, at what shares. Until then the page shows equal weights,
   labelled provisional.
2. **Board share for exploiters, synthetic styles and held-out styles now** (taken from training), or after the
   current generation closes.
3. **A training box for E9-18** and later training-mix runs. Any spend follows your standing rule (recap, then wait
   for your go).
4. **Disclosure**: if 6.3's measure shows a self-play understanding above noise, randomize it away or declare it on
   our card.
5. **Outside bots for the panel beyond BEN** (licence).

## 11. Tasks

On `team/gen9` (`tools/q show ID`):

| Id | What | Owner | Needs |
| --- | --- | --- | --- |
| E9-18 | Leave-one-bot-out: how well the net predicts a bot it never saw, and how that depends on the training mix's diversity | g9 | A training box or a small-net proxy (proposed) |
| E9-19 | Variance reduction for ratings, cheap version first (5.4) | g9 | Arena feeds' native boards |
| E9-20 | Diversity and redundancy of the current population: the three distances (3.2) and the threshold (3.3); done 13 Nov | g9 | Ladder cells, paired decisions from the feeds |
| E9-21 | Field choice and Nash average on the current cells (5.2); done 13 Nov | g9 | Ladder cells |
| E9-22 | A newcomer's "who" from the arrival mixture, and the learning curve (7.2, 7.3) | g9 | v2, arrival run records |
| E9-23 | Exploitability report for `8s-32` and `8x3-32`: the informed reader on the bench (6.1) | g9 | p41's pools, the bench |
| G9-B9 | Synthetic systems and styles generated from the card descriptor | bill | G9-B8 |
| G9-S8 | Carding styles with honesty by situation (deceivers), and the declared-understanding measure (6.3) | sam | E9-4 |
| G9-D10 | Page additions for a population (section 8) | dave, will | G9-D8, the cohort on the page |

## Sources

- Vinyals et al., "Grandmaster level in StarCraft II using multi-agent reinforcement learning", Nature 575 (2019),
  https://doi.org/10.1038/s41586-019-1724-z
- Balduzzi, Tuyls, Perolat and Graepel, "Re-evaluating Evaluation", NeurIPS 2018, https://arxiv.org/abs/1806.02643
- Burch, Schmid, Moravčík, Morill and Bowling, "AIVAT: A New Variance Reduction Technique for Agent Evaluation in
  Imperfect Information Games", AAAI 2018, https://arxiv.org/abs/1612.06915
- Strouse, McKee, Botvinick, Hughes and Everett, "Collaborating with Humans without Human Data", NeurIPS 2021,
  https://arxiv.org/abs/2110.08176
- Team results: `docs/gen9/STATE.md`, `reports/gen9-leakage-2026-11-12`, `docs/gen9/signals-results.md`, the board
  (`box/coordination:BOARD.md`) for plan's v2 post of 13 Nov 06:47 UTC

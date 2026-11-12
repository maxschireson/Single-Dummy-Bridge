# Gen 9: the arena as a population (design note, G9-D1)

> **Design in progress, dave, 12 November 2026. Nothing here is adopted.** Covers architecture
> section 6 and interfaces I1 and I7. The statistics (rating model, field score, promotion and
> futility test, admission width) are g9's (G9-A4) and have a slot in section 5.

**Changes to architecture section 7, in brief.**
(a) I1: a player package is immutable and carries no status; status lives in the registry log
(section 1). (b) I7: in phase 0 the epoch, player and snapshot ids go in each collector's cohort
manifest, which every record already names through `manifest_identity`, so the record format and
the collector runtime do not change (section 3). (c) I3, for g9: in a common auction the calls
were made by the common bidder, so the bidding part of each side's `PlayerModel` must be the
common bidder's declaration, while the carding part and experience stay the player's own.
(d) Ratings are kept per bidding condition (common and native).

## 0. What the data says (input to everything below)

The 62 registered feeds hold 43,031 boards under the dashboard's counting rules. Per-board noise
is pair-specific and heavy-tailed: SD 2.45 IMPs for `71s-32~7s-32` (79% flat), 3.2 for
`7s-32~6-32`, 4.0 to 4.5 between unlike bots; kurtosis 5 to 18 (Gaussian: 3). So noise is
estimated per pair, and the promotion test must hold under these tails (E9-5 bootstraps them).

## 1. Objects

| Object | Where | Writer | Mutable |
| --- | --- | --- | --- |
| **Player package** `player-package-v1` | `configs/players/<id>.json` on source (reviewed like plan files today) | Whoever proposes the player | No: a change is a new id |
| **Registry log** | `registry.jsonl` on the control branch | The controller, and people through it | Append-only |
| **Epoch manifest** `epoch-v1` | `epochs/<n>.json` and a `CURRENT` file on the control branch | The controller | No |
| **Collector registration** | `epochs/<n>/collectors/<name>.json` | Each collector, once per epoch | No |
| **Rating table** `ratings-v1` | `ratings/<n>.json` | The controller, at each look | New file per look |
| **Experience snapshot** | named by hash in the epoch manifest (G9-D5) | The controller, at the boundary | No |

The control branch is `arena9/control` for the prototype; people act on it through registry
events. Feeds stay one branch per cohort.

**Player package.** `id` (the bot id used in pair names, for example `71s-32`), `label`, `kind`
(`house`, `anchor`, `synthetic`, `outside`, `guest`), `bundle` (the full bot spec as it appears
in run manifests today: engine, settings, each net as a release folder plus sha256, so a cohort
is prepared from the package exactly as `prepare_gen7_alpha.py` builds bots from a plan),
`identity` (digest of the spec, the existing actor identity), `declaration` (Gen 8 system
package id, card IR id, carding descriptor), `lineage` (parent players; for every net, the
sha256 of its training-family list), `needs` (BEN server, TensorFlow, CPU seconds a board,
memory), `licence` (redistributable or not; nothing from EPBot/BBA). The 7.1 rollout lacked these:
its first Azure cohorts played only deals v4.1 was trained on and were closed by hand.

**Registry log events.** `submit`, `admit`, `activate`, `promote`, `demote`, `retire`, `protect`,
`unprotect`, `rules` (a new rules version), `runtime` (a new source commit for collectors). Each
event has a time, an author, an authority (a rule id and the evidence file's sha256, or a
person's words quoted), and takes effect at the next epoch boundary. A player's status
(`candidate`, `active`, `anchor`, `champion`, `retired`) is the fold of its events.

## 2. Epochs

An epoch is everything a collector needs, frozen: `epoch` (n), `id` (digest), `previous`,
`opened_utc`, `rules` (version and sha256), `source_commit` (the one runtime collectors run),
`players` (id, package sha256, identity, role this epoch), `schedule` (section 4: purposes and
integer pair weights), `conditions` (common bidder, regimes, audit and fork settings per
purpose), `deals` (a seed and a generator name; `exclude_families`, the union of every
scheduled player's training-family lists, by sha256), `experience_snapshot`, `end` (rule below)
and `events` (the registry events it applies).

**The next epoch is a function** of the previous epoch, the registry log up to the cut-off, the
pooled results up to the cut-off and the rules version. Anyone can recompute it and check the
controller. People change the arena only through events, never by editing an epoch.

**End rule** (defaults, to be tuned with E9-5): an epoch closes at the first of 4 hours, 6,000
pooled boards, or a decision reached (a promotion or futility bound crossed, an admission width
met) once it has run 45 minutes. The floor keeps collectors from spending their time switching:
the 7.1 preflight took 251 s, and draining takes up to one board's time on each worker.

**Deals.** `deal(seed_n, slot, k)`, the generator of `scripts/gen8_match.py` keyed by the epoch
seed, the collector's slot and a counter. A collector takes the first free slot once per epoch
by pushing its registration (the push is the lock, as for task leases), so no two collectors
play the same deal and nobody needs to know how many collectors there will be. This replaces
`--shard K/N`. A fresh seed per epoch makes deals fresh for every bundle by construction (a net
can only have trained on boards already played); `exclude_families` is the check. A board whose
family a rostered bundle trained on is still played but marked training-only for that bundle,
so its result is not counted in that bundle's ratings or tests.

## 3. What a collector does

A small follower next to the collector (a systemd timer on a box, polling the control branch
like boxctl does):

1. Reads `CURRENT`. Unchanged: nothing to do.
2. Changed: writes `STOP` on its cohort and waits for it to drain (boards in flight finish under
   the old epoch and count for it).
3. Registers for the new epoch (slot, feed branch name, host capabilities).
4. Prepares a cohort with `ops/prepare_epoch.py`: the existing run-manifest format, with `roster`,
   `bots` (from the packages), `pair_schedule` (from the epoch's weights, restricted to the pairs
   this host can seat), `corpus.jsonl` (the slot's deals), and new fields `arena_epoch`,
   `arena_epoch_id`, `arena_slot`, `players` and `experience_snapshot`. Cohort identity is the
   digest as today, so it changes with the epoch.
5. Preflights two boards, starts `ops/gen5_runtime.py`, publishes to `arena9-e<n>-<name>-feed`.

Because the epoch facts are in the cohort manifest, today's runtime, validator, exporter and
publisher run unchanged in phase 0. Per-record `arena` fields come when the runtime is changed
for other reasons (backlog item 1).

**Needed from the collector-runtime lineage** (backlog item 1; PRs #13 and #15, open): the
self-play regime, gap-fork and guess capture, feed-health heartbeats (which collectors are alive)
and BEN lanes. Until they are on one main-based runtime, the prototype (G9-D4) uses
`scripts/gen8_match.py`'s fork-free machinery on one machine.

## 4. Schedule

Shares by purpose, then pairs within a purpose. Defaults to be tested (E9-5 c):

| Purpose | Default share | Pairs and weights |
| --- | ---: | --- |
| Training | 55% | Champion self-play and champion against league members, by training value (fork yield) |
| Promotion tests | 20% | Each open candidate against the champion; more boards to tests whose bound is near |
| Evaluation panel | 15% | Champion against each panel member, equal |
| Admission | 10% | Each new player against the champion and two anchors until its rating width is met |

Weights are integers per pair (the runtime's `pair_schedule` is a repeated list). Between
epochs no pair's weight changes by more than a factor of two except at admission, promotion or
retirement (prospectus 15: cap weight changes). Purposes with nothing to do give their share to
training. A host that cannot seat a pair (no BEN server) skips it; the controller sees realized
counts per pair and raises those pairs' weights on capable hosts in the next epoch.

## 5. Ratings, admission, promotion, retirement

**Rating table** `ratings-v1`, one per bidding condition: per player a strength with its
interval and boards; per pair the model's prediction, the pair's own mean and SE, and a flag
where they disagree beyond the intervals (out-of-order match-ups); the field score against the
declared field mix with its worst cell. Inputs are the pooled rows with today's counting rules
(snapshot cut-off, a family once per pair, earliest wins, common and native apart).
*Model, field score and intervals: G9-A4.*

**Admission.** A `submit` event with a package. Checks by rule: identity reproduces from the
package, every net's sha256 matches its release, training-family lists present, needs met by at
least one registered host, licence redistributable, no `oracle` key anywhere in the spec
(test-only bots that are given the deal, E9-0), two-board preflight passes on a host.
Passing gives `candidate` at the next boundary and the admission share until the rating width
is met (*width: G9-A4*), then `active`.

**Promotion.** A candidate whose rating places it above the champion enters a promotion test:
the direct match by an always-valid sequential test with a futility bound, plus no panel cell
worse by more than the tolerance (*test, bounds, tolerance: G9-A4*). Crossing the upper bound
writes `promote` (the old champion becomes `anchor` or `active`, by rule); crossing futility
writes `demote` (the candidate stays in the league). Today's rule, "at least 1,000 boards and a
95% interval excluding zero", checked by hand at every look, is the baseline E9-5 measures.

**Retirement** by rule when a player has had the minimum share for three epochs (no pair with it
can change a decision) and it is not protected. Protected by default: the anchors (`ben`,
`ben64`, `1`, `5RZ32`), the last member of each declared system and each carding scheme, and
anything a person marks with `protect`. Packages, records and ratings stay.

## 6. Migration from today

| Today | Population arena |
| --- | --- |
| Plan file (`configs/round7*.json`): roster, `gen7_bots` builders, pair weights, notes | Player packages (built once) plus the epoch's schedule (derived) |
| Run manifest in each run folder | Unchanged format, prepared from the epoch; carries the epoch facts |
| Capsule (a drained run lending artifacts and unplayed deals) | Release folders named by packages; deals from the epoch seed |
| `--shard K/N` and `--exclude-families` by hand | Slots claimed per epoch; exclusions computed from lineage |
| "TO ALL COLLECTORS" on `BOARD.md`, stop rule checked by hand | `CURRENT` moves; the controller checks the rule |
| `gh-pages:arena/gen6-sources.json` edited by hand, fixed bot order in the dashboard | Collector registrations list the feeds; order from the rating table. The prototype does not touch `gh-pages` |
| `scripts/generation_results.py` pooling | The controller's pooling, the same rules |
| A generation number set in advance | A label put on a champion afterwards |

**Phases.** 0: control branch, packages for today's bots, controller and follower on one box,
runtime unchanged (G9-D4, G9-D6). 1: all collectors follow `CURRENT` once backlog item 1 is
merged. 2: per-record fields, synthetic players and guests admitted by rule.

**What stays a human decision:** the field mix that defines strength; the rules version (shares,
end rule, tolerances, test levels); anchors and panel membership; admitting outside bots and
guests (licence and disclosure); a new source commit for collectors (`runtime`), since code
changes are reviewed; any new box or other spend (Max's standing rule). Weight-only candidates
that run on the epoch's source commit can be admitted and promoted by rule.

## 7. Open points

- Whether ratings need a pair term (style match-ups): G9-D3 tests it on the published feeds.
- One champion, or a generalist plus specialists (prospectus 15).
- How much training should be against league members rather than self-play: a question for
  whoever trains the nets.

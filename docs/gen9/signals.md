# Gen 9 signals and card-play reading: design note (G9-S1)

> Design in progress, sam, 12 November 2026. Nothing here is adopted. Interfaces from
> [architecture.md](architecture.md) section 7 are kept; two additions to I5 and one to the
> experience labels are proposed in **bold** where they appear (sections 4, 5).

## 1. Situations and the signal that applies

Every hidden play is put in one situation from public information only (the play before it and
the contract). The chooser's carding descriptor (`configs/systems/_carding_fields.json`) then
names the signal, if any. A signal applies only on the **first round** of a suit (the first trick
in which that suit is led); later rounds carry no signal in v1.

| Situation (key) | When | Descriptor field | Signals in v1 |
| --- | --- | --- | --- |
| `lead.opening` | Trick 1, first card | `length_lead_vs_suit` / `_vs_nt`, `lead_from_ak`, `honor_sequence_lead` | the lead convention |
| `partner_lead` | Following, partner led the trick | `signal_on_partner_lead`; `attitude`, `count` for direction | attitude, count, suit preference |
| `declarer_lead` | Following, declarer or dummy led | `signal_on_declarer_lead`; `count` | count, suit preference, none |
| `first_discard` | The chooser's first card off-suit that is not a ruff | `first_discard`; `attitude`, `count` | attitude, count, Lavinthal, odd-even |
| `trump` | Following in the trump suit | `trump_signal` | count, suit preference, none |
| none | Later rounds, later leads, ruffs, Smith echo | | none |

**Facts** (what a signal states; computed on the chooser's original thirteen cards in a layout):

| Signal | Messages | Fact (v1 definition) | Spot for each message |
| --- | --- | --- | --- |
| count | even, odd | parity of the original length in the suit | standard: even = high, odd = low; upside-down reversed |
| attitude | like, dislike | holds the A, K or Q of the suit | standard: like = high; upside-down reversed |
| suit preference | higher, lower | of the two suits left after removing trumps, the suit led and (for discards) the suit discarded, the higher-ranking holds more HCP (ties: lower); no signal if three suits are left | higher = high |
| Lavinthal | higher, lower | as suit preference, between the two suits other than trumps and the one discarded | higher = high |
| odd-even | like, dislike | attitude to the suit discarded | like = highest odd spot, dislike = lowest even spot |

"High" is the highest spot of the class held, "low" the lowest. A message the holding cannot send
(odd-even with no odd spot) is treated as noise for that decision. Lead conventions are a card
rule, not a message:

| Holding in the suit led | `4th` | `3rd_5th` | `attitude` |
| --- | --- | --- | --- |
| Top two touching, the top a ten or better | top card; `rusinow`: the second; AK: per `lead_from_ak` (`rusinow`: K) | same | same |
| Doubleton | top | top | top |
| Three cards with A, K, Q or J | lowest | lowest | lowest |
| Three small | top | top | top |
| Four or more, no sequence | fourth highest | third highest from an even number, fifth (or lowest) from an odd | lowest with an honour, highest without |

The fact definitions are versioned (`signals-v1`). A real player whose "attitude" means something
else simply measures as less honest under v1; a later definition is a new version.

## 2. The class rule

A **class** is the set of a chooser's cards among which the choice is the signal.

- Opening lead: every card the chooser held in the suit led (the net says which suit, the
  convention which card; honours included).
- Every other play: the spots, two to nine, the chooser held in the suit of the card played. An
  honour (ten to ace) is a class by itself.

**E9-3 result (double-dummy proxy, true deal).** `arena-gen7-phase1-azure1-feed`, all 828
episodes, main tables only; every decision where the player held two or more spots in the suit
played. Defenders: in 1.49% ± 0.08% of 21,057 decisions the spots do not all take the same number
of tricks (hypothesis: at most 5%); when they differ, the worst costs 1.1 tricks on average, and the
lowest spot is among the best in 99.2% of all decisions. The exceptions are where expected: top
spot a nine 2.8%, an eight 1.2%, seven and below 0.9% or less; trump suit 3.2% against 0.9% in side
suits at suit contracts (2.1% at no-trump); ruffs 7.3% (not a signal situation); and most of all
when no card outside the chooser's hand still out ranks above the top spot (5.0% of 1,082),
against 0.25% with five or more above. They do not grow in late tricks (tricks 10 to 12:
0.6% to 1.2%). Declarer's own spots differ more often (3.6%),
which is one reason declarer plays are not read as signals. **The class rule stands as written for
v1.** A v1.1 option the data names: a spot with no outstanding card above it is its own class.
Details: `experiments/E9-3.md` on `team/gen9`.

## 3. Carding bots

A carding bot is a Gen 7 player (`engine: gen7`) with a new `tie_break: carding` and two new
keys: `carding` (a descriptor) and `honesty` (a value per situation key, or one value).

1. The search ranks the cards as now; `E` is its set of exactly tied cards.
2. The class is chosen as the house bot chooses: the net's likeliest card in `E`. If it is an
   honour outside the opening lead, it is played.
3. Otherwise `A` = the class members in `E`. If a signal applies and `|A| >= 2`: with probability
   `h` the spot the true fact prescribes within `A`, else a draw from the noise distribution
   (below); then with probability `eps` a uniform card of `A` instead. With no signal: uniform in `A`.

The bot only ever chooses among cards its own search rates as equal, so a signal costs it nothing
by its own estimate. **E9-3 shows that the search's ties hold every spot of the class in 91.5% of
defender spot plays** (search over 32 layouts separates spots more often than the true deal does).
The ties are a good guide to when spots matter: where they hold the whole class the spots split on
the true deal 0.10% of the time, where they do not 15.5%. So the bot signals only within them; in
those 8.5% it signals within a smaller set than the reader assumes (in 57% of them only one spot is
left), which the reader sees as a little dishonesty. A setting `signal_margin` (tricks below the best that still count as
equal for the class) is in the module, default 0, for E9-4 to try.

## 4. The reader term (I5)

For a hidden play `i` whose chooser belongs to a partnership whose `PlayerModel` has `carding`,
in each layout `x`:

```
log L_i(x) = phi * log sum over c in K_i(x) of q_i(c | x)         the class, from the net
           + log P_k(card_i | K_i(x), fact_k(x))                   the spot, from the carding rule

q_i(c | x)   = (1 - f) p_net(c | view_i(x)) + f / legal_i(x)        Gen 8's floor f, per card
K_i(x)       = the class of the card played, in the chooser's holding in x (held_then)
P_k(c | S, m) = (1 - eps) [ h_k r_k(c | m, S) + (1 - h_k) nu_k(c | S) ] + eps / |S|
nu_k(c | S)   = mean over messages m' of r_k(c | m', S)                 message form
```

`r_k(c | m, S)` is 1 for the spot that message `m` prescribes in holding `S` (section 1) and 0
otherwise. For the opening lead `r` is the convention's card and `nu` is uniform over the suit.
No signal: `P = 1 / |S|`. Honour classes: `P = 1`, so the term is Gen 8's with factor `phi`.
Everything in the second line is per layout: the holding, `|S|`, the fact. A forced card and a
singleton class score 0.

- **Message form for the reader and the bot alike.** Noise picks a message, not a spot, so with
  three or more spots noise does not read as "high" more often than "low". The bot draws from
  exactly this distribution, so in E9-4 the reader's model is the bot's when given the true `h`.
- **Who is read this way.** Any hidden chooser whose model has `carding`: opponents, and also
  partner when partner's model declares carding (E9-6). Declarer's and dummy's plays keep Gen 8's
  form with `phi`. A model that is `plain`, or has no `carding`, gets exactly the Gen 8 term
  (tested). House bots have no descriptor, so they are read by the net in full, as now.
- **Vectorized.** `held_then` already gives `[layouts, 52]` per play. The original hand is
  `View.original` plus the chooser's played cards; parity, honours and HCP per suit are sums over
  52-column masks; highest and lowest spot are `argmax` over the class mask. The net is called on
  exactly the rows Gen 8 calls it on; the cache keyed by the held-cards mask stores the class
  log-mass beside the card's log-probability. No new net calls.
- **Where it enters.** `Gen9PlayReader`, a mixin on `Gen7Player` that holds the table's
  `PlayerModel`s (given through `meet`): its `play_log_likelihood(o, view, assign, plays)` returns
  the per-layout sum, a drop-in for `Gen7Player.play_log_likelihood` in
  both `weighted_layouts` (deal list) and `early_layouts` (before it). **Proposed addition to I5:
  `play_log_terms(...) -> (net_part, signal_part)`, so that the player shell (G9-A3) can apply
  `play_weight` to the net part only.** The signal part is a calibrated likelihood and should not
  be tempered by an exponent fitted for the net (8s-32 uses 0.5). With `play_weight` 1 (8x-32) the
  two are the same. The early pool's halving of the exponent when too few layouts fit stays on the
  sum: it is a guard, not a calibration.

## 5. Estimators from finished boards

All hands are known after the board, so every quantity is exact.

- **Honesty per situation key** `k`: experience `count` named `card.<k>` (for example
  `card.partner_lead.attitude`, `card.lead.opening`), with g9's labels `hit/<n>` and `all/<n>`,
  `n` = number of messages (2) for signals and number of cards in the suit for leads. An occasion is
  a play in a situation with a signal, two or more class cards held, the message sendable; a hit is
  the card the true fact prescribes. **Proposed: also `hit/<n>/<s>` and `all/<n>/<s>`, `s` = class
  size,** so that the floor `eps` is allowed for exactly (the aggregate labels alone read `h`
  low by about `eps`). Estimate: posterior mean on a grid with a Beta prior centred on the
  profile's value, worth 8 occasions (`experience.choice_honesty` on the aggregates; an exact
  version beside it).
- **Play factor `phi`**: `moment` named `play.info` (for carding players, the class term only) on
  the grid 0, .1, .2, .3, .5, .75, 1, 1.25, 1.5: per decision where we read this player's plays,
  the gain in the true layout's log weight from those plays at each factor (Gen 8's measure),
  with the signal term in place at the current honesty. `grid_best` with the prior on the
  profile's curve (house: best at 1; unknown: Gen 8's 0.3), worth 100 decisions. Honesty is
  estimated first (it needs no net), then `phi` given it.
- **Learning curve (G9-S5):** reading gain on fresh boards against boards of experience, N = 0,
  25, 50, 100, 200, 1,000.

## 6. How the experiments are measured

| Experiment | Form | What is measured, and how |
| --- | --- | --- |
| E9-3 | (no model) | Done: section 2. Script `scripts/gen9_spot_equivalence.py` on `research/gen9-spot-equivalence`. |
| E9-4 part 1 | message form | **Without a box, on recorded boards: relabel the defenders' spots.** At each recorded defender decision whose tie set holds two or more class cards, re-choose the spot by the carding bot's rule (scheme, `h`) from the defender's true hand, and swap the two cards' order of play for the rest of the board; the swap is kept only if every trick's winner is unchanged (else the recorded card stays). The defenders' spot play is then exactly the carding bot's on real deals; declarer's decisions are scored by the `gen8_play_info.py` method under each reader (net at 0.3, net at 1, signal model with true `h`, with `h` from N boards). Thousands of boards per cell in the sandbox; the limit is that nobody reacts to the signals, which a prediction metric does not need. |
| E9-4 part 2 | message form | Played boards on a box, as registered. |
| E9-6 | message form, `h` = 1 | Same module: a carding bot whose partner's model declares the same scheme reads partner's spots with the signal term. Played boards on a box. |
| E9-7 | estimators only | Section 5 applied to BEN's recorded cards: `play.info` by role and trick band (named `play.info.<role>.<band>`), and `card.<k>` counts against the standard and upside-down descriptors (does BEN signal, and which way). Same code as G9-S6. |
| G9-S6 | estimators only | The house bots' adherence to each standard scheme by situation key: their carding card, and how much of the net's spot reading is convention. |

## 7. Not in v1

Continuations (the second card of a high-low, present count), Smith echo, doubleton attitude at
suit contracts, suit preference at no-trump with three suits left, conventions for later leads
and returns, honesty that depends on what partner needs (keys by situation allow it later), a
model of declarer's falsecards beyond `phi`, and our own bots choosing when to signal honestly.

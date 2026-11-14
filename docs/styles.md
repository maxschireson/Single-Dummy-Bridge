# Styles and personas

Bots should not all play or bid alike: a bot that has met one opponent many times reads its cards and calls better than
bridge logic allows, and that reading is counted as strength. So bots get personalities, mostly directed and a little
random. Max, 03:35 to 03:50 UTC on 14 November 2026: personalities costing "half an imp or so" should be well
represented, "with some who give up an imp even"; then, of the average over a mixed population, "Half an imp that I
suggested before was too much". The population average aimed at here is about a quarter of an IMP a board (our reading,
not his number).

| Module | What |
| --- | --- |
| `bridge_harness/style.py` | Card-play styles: `tempo`, `active`, `high`, plus a `random` share, among the cards the bot rates within its margin (`near_tie` for a search bot, `mix.near` for a rollout bot) |
| `bridge_harness/bid_style.py` | Bidding styles: `aggressive`, `shape`, plus `random`, among the calls the bidder rates within `near` (Max, 19:31 UTC on 14 November) |
| `bridge_harness/persona.py` | A bot's play and bidding styles together, its partner's knowledge of them and what its opponents are told |
| `scripts/bid_style_cost.py` | What a bidding style costs, double dummy, and whether it moves the auction the way it says |

## Bidding styles

A bidding style does not change what the bidder thinks a call is worth. Among the legal calls whose probability is at
least `exp(-near)` of the best call's (the cap), it takes the call with the highest `log p + a_eff * action`, and a
`random` share of the time draws one of them from the bidder's own probabilities (the first version drew uniformly: at
`near` 6 a 15% uniform share alone cost 0.17 IMP a board, most of a persona's budget spent on noise).

- **aggressive** (more bidding > 0, less < 0). A call's action: pass 0, double or redouble 0.5, a bid 1 plus the levels
  it goes beyond the cheapest legal bid in its strain. The weight is an exchange rate: one step of action is worth `|a|`
  nats of the bidder's log probability (with `a = 1` the style bids a level higher whenever the bidder rates that call
  at least 37% as likely as the lower one). The first version took the close call with the most (or least) action
  whatever the weight, so only the sign and `near` mattered, and a reader told half of a style read it as all of it.
- **shape** (values shape > 0, high cards < 0). It moves the aggression for this hand: a shape bidder adds
  `s * z_D` (distribution points: one a card past four in a suit, void 3, singleton 2, doubleton 1; standardised, exact
  mean 2.575 and sd 1.764 over all hands), a points bidder adds `|s| * z_H` (high-card points, mean 10, sd 4.13), each
  clipped to [-2, 2]. Across hands it averages zero: it changes which hands bid more, not how much.

`bid_style.distribution` gives the exact probability of every call under a style (what a reader needs), and
`bid_style.scaled(style, f)` the style as a reader who knows a share `f` of it models it.

Hooks: `scripts/gen8_match.py` gives a bot whose spec has `bid_style` its own `StyledBidder` (bidders are shared between
bots that use the same net) and records each styled call as behaviour `styled` with its probability under the style.
Only BEN-format nets (`predict`) can be styled; system bidders (`call`) give no probabilities. The play server
(`play/sidplay/engine.py`) does the same for a bundle whose spec has `bid_style`.

## Personas: knowledge, disclosure, correlation

Max, 04:02 to 04:10 UTC on 14 November (for play styles; at 19:31 UTC the same for bidding). Per dimension:

- **knowledge**: the share of the style the partner knows, 0 to 80% (the partner reads a styled bot with each weight
  times this share);
- **disclosure**: what the opponents are told, usually 75% of the partner's knowledge, from 0 to 150% of it (mode 0.75);
- correlated across dimensions: one correlation per persona, triangular on [-0.2, 0.8] with mode 0.6, for the latent
  normals behind the knowledge shares and behind the disclosure ratios.

`persona.draw` makes one (bidding dose: `bid_near`, a margin or a range drawn per persona, and `bid_scale`, the
bidding weights uniform on `[-bid_scale, bid_scale]`); `persona.view(persona, 'partner' | 'opponent')` gives the styles
as each should model them; `persona.disclosure_text` puts the disclosed part in words.

**Partial knowledge of a card-play style.** `style.py` keeps the best-scoring cards among the near ties, so only the
ratios between a play style's weights matter: multiplying every weight by the same share changes nothing, and a reader
who knows 30% of a one-dimension play style models all of it. For play, `view`'s scaled weights are only meaningful
across dimensions; the reading that gives a share its meaning is a mixture (the style in force with probability equal to
the share, the plain choice otherwise). That is for whoever builds the readers; `style.py` is unchanged, since the
loop's self-play uses it.

**Not built yet:** the readers. The belief nets, the hand-fit scorer and the rollouts' opponent models read every bot
as unstyled, so for now no partner uses its knowledge and no opponent its disclosure. Reading a styled bidder means
weighting the layouts a reader samples by `distribution` under the view's style against the plain bidder's choice.

## Variable personalities and identifiers

Max, 21:14 UTC on 14 November: "Update Sid to randomize personalities. Partnership personalities should be independent,
but somewhat correlated - .5 ... SidVariable can be an identifier, and when playing against variable personality bots
the system should by default use their identifier. This should balance trying to make informed inferences with
information leakage. It can ask their partner for estimated styles, and can act on the (to be publicly known) level of
variability and disclosure. We should update gen 8/9 to also uptake this personality capability."

- **Partnerships** (`persona.draw_partnership`, `persona.seats`): each latent draw of a persona is correlated 0.5 with
  the matching draw of its partner's; opposing partnerships are independent; the correlation across dimensions is drawn
  once per partnership. Each persona alone is distributed as `persona.draw` gives it.
- **Identifiers**: a variable population has one bot id (`SidVariable`, `Gen8Variable`; `persona.KNOWN`, plus a match's
  own `variable_ids`). Every other bot meets it by that id, never by its persona; a blind 8X bot is still told it
  (`x8.read_variable`, default on), since it gives away only the population. What anyone may know about the population
  is `persona.public(identifier)`. What the partner says when asked is `persona.view(p, 'opponent')`
  (`persona.describe(p, 'opponent')` in words); the partner itself reads `view(p, 'partner')`.
- **At the table**: `Gen7Player.table_styles` / `X8Player.table_styles`, `{seat: {'play': style, 'near': margin}}`, set
  per table. A Gen 8 search seat chooses among the cards within the spec's `near_tie` (0 for `Gen8Variable`: exact
  ties); an 8X seat among its rollout candidates within `near` (`persona.PLAY_NEAR_X8`, 0.05 tricks, not calibrated; the
  loop's note on `stu3-pm` puts a uniform choice within 0.05 at up to 0.09 tricks a board by the rollouts' own values,
  an overstatement). A persona's random share takes one of them at random. Seats without a persona play as before.
- **Gen 8 and 8X in matches** (`scripts/gen8_match.py`): a bot whose spec has `"persona": {"variable": true}` (optional
  dials: `bid_near`, `bid_scale`, `bid_random`, `play_random`, `play_near`) gets, on every board, an independent
  partnership on each side drawn from (seed, board, bot id): its seats' play styles through `table_styles` and its
  bidding styles through its bidder (`VariableBidder`). The record keeps them under `personas` (true styles, knowledge,
  disclosure). `configs/loop-bots.json` (from `make_bots.py`) has `SidVariable` (stu4c-put with a persona; it floors
  its own kind's guaranteed contracts) and `Gen8Variable` (8p-32-v41 at margin 0 with a persona).
- **Gen 9** (`feature/gen9`, g9's branch): its player is built on Gen7Player, so it takes `table_styles` once its base
  has `style.py`, `persona.py` and this Gen7Player; its PlayerModel is where a reader would use a disclosure.
- **Not built**: readers acting on the disclosures. Today a reader uses the identifier (its settings keyed by it, the
  `'*'` value where it has none) and nothing else of a persona.

## Dose

`scripts/bid_style_cost.py`: each deal bid twice by the Gen 6 bidder (the one SiD (rollout) Stu bids with), plain at
all seats and with North-South styled, scored by double-dummy tricks. Results: `reports/bid_style_cost_2026-11-14.md`.
The persona defaults (`near` 6, bidding weights uniform on ±3) cost a mixed population 0.24 ± 0.03 IMP a board on
12,000 deals; a single style at weight ±2 costs 0.12 to 0.21.

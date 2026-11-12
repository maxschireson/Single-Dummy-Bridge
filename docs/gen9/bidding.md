# Gen 9 bidding: card IR, compile, the rule filter, profiles

> Design note for G9-B1, by bill, 12 November 2026. **Nothing here is adopted.** Code it refers to
> is on `feature/gen9-bidding-cards` (`bridge_harness/cards/`, `configs/cards/`, `tests/test_gen9_cards.py`).

**Changes to architecture section 7, first.** (1) I2: the card IR's rule layer is the compiled
*meanings* below, executed directly; rule-bidder `Settings` become an optional `generator` block for
a card inside that family, not the rules. (2) I4: signature unchanged; the filter also exposes
`seat_terms` (which calls it covers) and an explanation per call for check sheets. (3) Section 4.2:
the first measurement (section 5) says the filter must **not** simply be multiplied onto a profile's
scorer: on foreign systems the scorer's misreadings survive the product, and on the house system an
approximate card costs weight. Proposed: a `card-only` profile in the 4.1 mixture, and the filter
restricted to *residual* contexts on a matched profile (section 3).

## 1. Card IR, bidding part

One document per card, `configs/cards/<id>.json`:

- `descriptor`: flat `field: value` pairs. The controlled list is `configs/cards/_fields.json`
  (`card-fields-v0`, 81 fields): 51 compile into meanings today, 30 are recorded but not executable
  (Smolen, Puppet Stayman, Lebensohl, Drury, Bergen, new-minor forcing, fourth suit, criss-cross,
  Walsh, Mini-Roman, Muiderberg, responsive/maximal/support doubles, defences to preempts, strong
  clubs and two-suiters, DOPI/ROPI, exclusion, Kickback, psychic policy, forcing pass,
  brown-sticker flags). A field has a default, so a card states only where it departs from the
  base (five-card majors, 15-17 1NT, strong 2C, weak twos, 2/1). Nested JSON is also accepted.
- `provenance`: source format and file, reader, confidence per field, and the card text the reader
  could not place. Unplaced text and non-executable fields form the card's **declared residual**.
- `generator` (optional): rule-bidder `Settings` when the card lies inside that family, so the arena
  can field a player for it; or a pinned bidder of another kind.
- Carding fields: Gen 8's `configs/systems/_carding_fields.json` (sam owns them).

Real cards. ACBL card: general approach; 1NT range(s) by seat and vulnerability, five-card major
allowed, responses (Stayman, transfers, Texas, 2S, 3-level, Smolen, Lebensohl), system on over a
double; major and minor openings by seat with expected length, raises (single, limit, Jacoby 2NT,
splinter, Bergen), 1NT forcing or semi-forcing, 2/1 game force; 2-level openings with ranges and
conventions; overcall ranges, jump overcalls, direct cue-bid, unusual 2NT, defence to 1NT; negative,
responsive, support doubles and their limits; slam conventions; leads and signals. WBF card: the
same plus a table of every opening (artificial or not, minimum length, HCP), psychic policy and
"special bids that may need defensive preparation". USBF system summary: the WBF facts in prose plus
the unusual-methods flags. G9-B6 reads three such cards; the field list grows with what they need.
Intake (an agent): fill the descriptor and provenance, then generate the check sheet (what the
compiled card opens and responds on 40 fixed hands) for a person or the card's owner to confirm.

## 2. Compile

`CardSystem(card).rules(ctx)` returns, for one context seen from one seat, the calls the card
defines there as **rules in priority order**, or `None` when the card does not cover it. A rule is
`(call, predicate, family, forcing, artificial)`. A predicate is a disjunction of clauses (a Polish
1C, a Multi 2D) and a clause is intervals on features of the hand type (HCP, four lengths,
balanced/semi-balanced, longest/second/shortest, rule-of-20 and rule-of-15 sums, A-K-Q and A-T
counts per suit, stoppers, controls, key cards for a trump suit, losing tricks) plus relations
between suit lengths (hearts ≥ spades). Every feature is a function of lengths and honour bits, so
a predicate is evaluated on a whole layout pool at once, identically on types and on 13 cards
(tested on 10,000 hands).

Covered contexts (v0): openings by seat and vulnerability; responses to one of a suit, 1NT, 2NT,
strong 2C, weak twos and a strong club; opener's first rebid (after one-level responses, 1NT, raises,
Jacoby 2NT, 2C-2D, 2NT asks); the no-trump relays and responder's next call; direct and balancing
overcalls, takeout doubles, Michaels, unusual 2NT, defence to 1NT (natural, Cappelletti, DONT,
Landy); responses after a double or an overcall (negative doubles, cue-bid raises); advances of
overcalls, doubles and two-suiters; key-card and Gerber answers. Every covered context ends with a
catch-all, so a compiled table is **complete**. Five cards compile today: 2/1, SAYC, Acol, Precision,
Polish Club. A card's own bidder (`cards/bidder.py`, first satisfied rule; uncovered contexts to a
fallback) never breaks its card on covered calls (tested on 150 deals a card).

Required fields: `id`. Everything else defaults. Refused: values outside a field's range (a 1NT
outside 8-22, an unknown two-level type), and anything from the EPBot/BBA engine or its card files.

To rule-bidder `Settings` (for the `generator` block): style, club_min, open_min, limited_max, one
1NT range, nt_five_major, two_clubs_len, two_diamonds, weak range, preempt_len, neg_max,
two_over_one, overcall and takeout minima, NT-overcall range, weak jump overcalls, Stayman,
transfers (the `settings` column of `_fields.json`). A card that needs four-card majors, a
multi-way 1C, Multi, Flannery, inverted minors, Jacoby 2NT or seat/vulnerability-dependent 1NT
ranges has no Settings form; it still has meanings, and my bidder is its generator.

Relation to `rule_bidder.py` (g9's decision: by test, not shared code): I write IR cards for its
precision and standard settings and three sampled variants and test that its auctions never break
them on covered calls (G9-B2). For experiments only, `cards/rb_meanings.py` lifts its tables into the
same rule form (its private tests evaluated on a hand built from the type), which is the exact
reading of that generator, i.e. E9-1's ceiling.

## 3. The rule filter, exactly

For each call `c` that seat `s` made in context `t`:

```
rules R_t = card.rules(context t)                         # None: the card says nothing -> term 0
if c not listed in R_t:                       term 0      # the card has no meaning for c here
first(h) = first rule whose predicate h satisfies          # complete tables: always defined
d_r(h)   = distance from h to rule r's predicate           # HCP points, cards of length (x1.25), shape (x2) ...
P(c | h) = (1 - eps_f) * [first(h) is a rule for c] + eps_f * softmax_r(-lam * d_r(h))[c]
F_s(h)   = sum over covered calls of log P(c | h)
```

- The indicator carries the call's own meaning and **negative inference** (h fit an earlier rule):
  a first-seat pass denies an opening, a 1C opening denies a 1NT hand. It is used only where the
  table is complete; for the rule bidder's tables, which are not (a hand that fits nothing goes to
  its general procedure), such a hand contributes 0.
- **Soft edges**: in the `eps` term an off-by-one hand costs less than a hand that is wrong by
  five points or a suit. `lam` = 1.5 per unit of distance.
- `eps_f` is per **family** of calls (about 40 in the compiled tables: `open_nt`, `open_major`,
  `open_weak`, `resp_raise`, `resp_nt_relay`, `comp_overcall`, `comp_double`, `resp_comp`,
  `adv_overcall`, `rebid_nt`, `ask_answer`, ...), per player: a Beta posterior from experience,
  prior 0.05 with weight 20.
- **Inert**: no card gives exactly zero (`NoCard`; tested).
- Combination with the 4.1 mixture, changed by the measurement: per profile `k` the seat term is
  `S_k + F` on the card's **residual contexts** of `k` (contexts where `k`'s generator breaks the
  card more often than a threshold, from matching, section 4) and `S_k` elsewhere. One extra
  profile, `card-only` (`F` everywhere, no scorer), is always a candidate, so a foreign system read
  under a natural profile is handed to the rules seat by seat by the posterior; single calls are
  handed over after G9-B5 (dropped-call scorer).
- Cost: rules are compiled once per context and cached; a predicate is a few vector comparisons.
  One seat's filter over 20,000 types for a 3-5 call auction: about 1 million types a second on
  one sandbox core (2/1 and Precision cards), well below the scorer's cost. The rule bidder's
  tables through `rb_meanings`: 7,000 types a second cold (its tests run per type), 300,000 warm.

## 4. Profiles, matching, detection (G9-B4)

First profiles: house-gen6, house-gen5, house-dds40k (generators: their nets; no card), the five
compiled cards, the rule bidder's precision and standard settings and sampled variants, and
`card-only`. Reference rules for a house profile: none; it is matched to cards, not the reverse.

Distance (architecture 3): bid N fixed deals with profile `k`'s generator; over the calls the card
covers, the share that the card's rules would not make (first satisfied rule ≠ call), weighted by
how often the context arises. Reported per context family, which gives the **residual** list.
Card-to-card distance uses the same procedure with the other card's bidder.

Detection: on a finished board all hands are known, so the likelihood of the pair's calls under a
profile is exact: for card and rule profiles the noisy-rule `P(c | h)` above; for net profiles the
bidder net's own softmax for each call. Posterior over profiles plus `unknown` (a flat call
model), multiplied board by board, tempered by the per-family `eps`. E9-2 measures boards to 0.95.

## 5. Measured so far (prediction only; `reports/gen9-filter-prelim-2026-11-12`)

Gain in nats of the true hand's weight over a uniform pool of 256 random hands (one seat, seen by its
left-hand opponent), 1,600 seat decisions per system: scorer v0 `S`, filter with the system's
own card `F` (eps 0.05), both, the scorer at half weight with the filter.

| Auctions bid by | S | F | S + F | ½S + F |
| --- | ---: | ---: | ---: | ---: |
| house Gen 5 bidder (card: 2/1, approximate) | 2.18 | 0.85 | 1.77 | 1.61 |
| 2/1 card / SAYC card | 0.61 / 0.75 | 1.68 / 1.67 | 0.97 / 1.08 | 1.56 / 1.60 |
| Acol card / Polish Club card | −1.34 / −1.16 | 1.65 / 1.43 | −0.55 / −0.72 | 0.97 / 0.72 |
| Precision card | −2.49 | 1.42 | −1.90 | 0.18 |
| rule bidder standard / precision (exact tables) | 0.39 / −2.55 | 1.58 / 1.71 | 0.68 / −1.73 | 1.38 / 0.37 |

Standard errors 0.03 to 0.23. On unseen systems the generic scorer is worse than nothing; the
product recovers 0.3 to 0.8 nats of gaps of 1 to 4; on house auctions an approximate card costs 0.42
nats (0.25 with `eps` learned per family from 1,500 house boards). This is why section 3 changes 4.2.
E9-1 proper (G9-B3) uses the registered protocol (512 layouts from the prior, leader and declarer
views, the three readers plus the ceiling), then played boards on a box.

## 6. For experience-v1 (G9-A2)

Per covered call on a finished board: `{player, board, family, context key, call, card's call,
agreed, deviation}` where `deviation` is the signed miss on the nearest clause of the card's rule
for the call made (for example `hcp: -1` for a 14-point 1NT on 15-17), so range ends can move per
player. Merged store: per `(player, family)` agree/deviate counts and per `(player, rule, feature)`
a histogram of signed misses. Profile log-likelihoods per board for detection.

## 7. Open

Coverage beyond the declared layer is the fallback's (rule bidder's general procedure); our own
calls' meanings do not yet depend on the opponents' card (a cue-bid of an artificial 1C); the
house profiles' residual lists need the matching run; per-call handover waits for G9-B5.

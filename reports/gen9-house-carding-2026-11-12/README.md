# G9-S6: the house bots' own carding, measured

Gen 9 research (sam, signals), 12 November 2026. Experiment file: `experiments/E9-9.md` on
`team/gen9`. Kind of evidence: exact counts on recorded boards (all hands known afterwards).
Nothing adopted.

**Data.** `arena-gen7-phase1-azure1-feed` at `f9dad79`, all 828 episodes, 1,824 main tables;
defenders are the house bots 7s-32 (Gen 7 standard), 6-32 (Gen 6 fast), 5RZ32 (Gen 5) and 1.

**Spots: no agreed signals.** For every signalling occasion (a situation, two or more spots of the
class held), the share of high spots when the true hand calls for one message minus the share
when it calls for the other (`association.json`, `scripts/gen9_house_signal_association.py`).
Zero means the spot says nothing about that fact.

| Bot | Signal (fact) | Occasions | High spot, first message | High spot, second | Difference |
| --- | --- | ---: | ---: | ---: | ---: |
| 7s-32 | Attitude, partner's lead (like / dislike) | 729 | 0.23 | 0.22 | +0.007 ± 0.032 |
| 7s-32 | Count, partner's lead (even / odd) | 729 | 0.23 | 0.22 | +0.013 ± 0.031 |
| 7s-32 | Count, declarer's lead (even / odd) | 1,474 | 0.27 | 0.24 | +0.029 ± 0.023 |
| 7s-32 | Attitude, first discard (like / dislike) | 1,030 | 0.27 | 0.25 | +0.024 ± 0.028 |
| 7s-32 | Count, first discard (even / odd) | 1,030 | 0.30 | 0.22 | +0.079 ± 0.027 |
| 7s-32 | Lavinthal, first discard (higher / lower) | 1,030 | 0.21 | 0.29 | -0.080 ± 0.027 |
| 7s-32 | Count, trumps (even / odd) | 503 | 0.24 | 0.27 | -0.024 ± 0.039 |
| 7s-32 | Suit preference, partner's lead (higher / lower) | 568 | 0.23 | 0.21 | +0.021 ± 0.035 |
| 7s-32 | Suit preference, declarer's lead (higher / lower) | 976 | 0.26 | 0.27 | -0.006 ± 0.028 |
| 6-32 | Attitude, partner's lead (like / dislike) | 210 | 0.28 | 0.27 | +0.009 ± 0.064 |
| 6-32 | Count, partner's lead (even / odd) | 210 | 0.28 | 0.28 | +0.002 ± 0.062 |
| 6-32 | Count, declarer's lead (even / odd) | 411 | 0.32 | 0.25 | +0.071 ± 0.044 |
| 6-32 | Attitude, first discard (like / dislike) | 328 | 0.30 | 0.26 | +0.040 ± 0.050 |
| 6-32 | Count, first discard (even / odd) | 328 | 0.31 | 0.26 | +0.050 ± 0.051 |
| 6-32 | Lavinthal, first discard (higher / lower) | 328 | 0.25 | 0.31 | -0.060 ± 0.050 |
| 6-32 | Count, trumps (even / odd) | 145 | 0.27 | 0.23 | +0.037 ± 0.072 |
| 6-32 | Suit preference, partner's lead (higher / lower) | 168 | 0.29 | 0.24 | +0.057 ± 0.069 |
| 6-32 | Suit preference, declarer's lead (higher / lower) | 257 | 0.28 | 0.27 | +0.020 ± 0.057 |

5RZ32 and 1 are in `association.json`; every difference there is within ±0.12, and only one is
more than two standard errors from zero (bot 1's first discard, -0.11 ± 0.05, toward "low from
even"). With 36 bot-and-signal cells, one or two at that level are expected by chance. Over all four bots, the
spot played is the lowest of the class about 60% of the time, the highest about 25%, a middle
one about 15%. The largest effect is 7s-32's first discard (+0.08 ± 0.03 toward "high from even",
-0.08 toward Lavinthal); it is small next to a signal at honesty 0.5 (a difference of 0.5).

**Opening leads: a fourth-best habit.** The card led, against each convention's card for the
holding (`house_carding.json`, `scripts/gen9_house_carding.py`; chance is the mean of 1/cards held):

| Bot | Leads | Fourth best | Third and fifth | Attitude | Chance |
| --- | ---: | ---: | ---: | ---: | ---: |
| 7s-32 | 853 | 0.48 | 0.35 | 0.31 | 0.30 |
| 6-32 | 256 | 0.45 | 0.31 | 0.28 | 0.30 |
| 5RZ32 | 288 | 0.41 | 0.25 | 0.22 | 0.30 |
| 1 | 284 | 0.39 | 0.43 | 0.39 | 0.30 |

From AK the ace is led 167 times in 179, and from other touching honours the top card 192 times in
295. (The three conventions share the honour-sequence and doubleton rules, so they agree on many
holdings; the differences between columns come from the long-suit spot leads.)

**Draft carding descriptor for the house system package** (what an opponent is owed):

```json
{"length_lead_vs_suit": "4th", "length_lead_vs_nt": "4th", "lead_from_ak": "ace",
 "honor_sequence_lead": "top", "signal_on_partner_lead": "none", "signal_on_declarer_lead": "none",
 "first_discard": "none", "trump_signal": "none"}
```

with a note: "No agreed spot signals. Among equal spots the lowest is played about 60% of the
time; the spot carries no reliable information about count, attitude or suit preference. Opening
leads are fourth best from length about half the time (honesty about 0.25 against fourth best)."
House bots keep the net's own reading of each other, so the descriptor is for disclosure and for
other players' readers, not for the house reader.

**What it implies.** The house bots' spots are nearly uninformative, so (1) a reader gains little
from reading them by any scheme, and Gen 8's discount on foreign spots costs little against house
bots; (2) E9-6 (designed signals for the house pair) starts from a defence that signals nothing.

**Limits.** One feed; the house bots choose spots only among cards their search ties, which this
measures against the whole class held (the cut to the tie set is in `house_carding.json`, rows
`|ties|`: hit rates differ from the whole class by at most 0.04 for spots and 0.09 for leads).

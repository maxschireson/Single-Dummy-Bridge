# Card intake bundle: sample-a-acbl-photo

Made by `scripts/gen9_card_intake.py v0 (G9-B8)` on 2026-11-13 09:52 UTC. Procedure: docs/gen9/card-intake.md.
Layout guessed: **acbl** (signature headings found: {'acbl': 4, 'wbf': 0}).

Read every field against the page images; the text below is an aid. Suit symbols: none decoded; read every symbol-bearing field from the image.

OCR against the PDF text layer: 80.3% of the reference's 513 words of 3+ letters are in the OCR text.

## Pages

- `pages/acbl-sample-a-p1.png` from `samples/cards/acbl-sample-a-p1.png`: 311 lines, ocr (tesseract, psm 11), mean word confidence 71.9

## acbl-sample-a-p1.png

### SPECIAL DOUBLES

Fields this section feeds:

- [ ] `comp.negative_double_thru` (compiled; default "2S")
- [ ] `comp.responsive_double_thru` (recorded only)
- [ ] `comp.maximal_double` (recorded only)
- [ ] `comp.support_double_thru` (recorded only)
- [ ] `comp.snapback` (recorded only)

```
SPECIAL DOUBLES
After Overcall: Penalty
Negative i
thru.
Responsive ll
thru
4H Maximal
Support: Dbl. thru 2x-1 Redbiil
Card-showingM™ Min. Offshape T/OL)
Snapdragon. Stolen Bid
```

### NOTRUMP OVERCALLS

Fields this section feeds:

- [ ] `comp.nt_overcall` (compiled; default [15, 18])
- [ ] `comp.balancing_nt` (compiled; default [11, 14])
- [ ] `comp.balancing_nt_major` (compiled)
- [ ] `comp.unusual_2nt` (compiled; default true)

```
NOTRUMP OVERCALLS
Conv.(| Sandwich by PH only
Balancing: 11 to 1406
Jumpto2NT: Minors) 2Lowestlll
z
Conv.-] Balancing 2N=19-21
```

### (before any heading)

```
Direct: 15 to 18 Systems onl Ls | as——n
.
Le
VERY LIGHT: Openings)
to
21
Puppet Stayman-
Transfer Responses:
Jacoby Texas ll
Pup to 3N with
-K Ist-3rd
Conventional NT Openings
```

### GENERAL APPROACH

Fields this section feeds:

- [ ] `resp.two_over_one` (compiled; default "gf")
- [ ] `open.min_hcp` (compiled; default 12)
- [ ] `open.third_seat_min` (compiled; default 10)
- [ ] `open.strong_2c` (compiled; default {"hcp": 22, "ltc": 3, "ltc_hcp": 17})
- [ ] style: statements of seat, vulnerability or strength (style list; variants where a field holds them)

```
GENERAL APPROACH
card M, 2/1 GF. Frequently respond with <6 HCP.
Two Over One: Game Forcing) Game Forcing ExceptWhen SuitRebid
3rd Handl)
Overcalls
Preempts 1)
FORCING OPENING: i || 24MM Natural2Bids—
Other
2NT _ 20
3a
minor(s) Slam try
3NT Gamb to_ ling
No out:
le
XX forces 2#/Pen X
```

### DEFENSE VS NOTRUMP

Fields this section feeds:

- [ ] `comp.vs_nt` (compiled; default "natural")
- [ ] `comp.vs_nt_double` (compiled; default "penalty")

```
DEFENSE VS NOTRUMP
Strong 14+
Wk min <14
vs:
ae
Majors
Same
2¢
One major
Same
av
Sv+m
Same
2a
Sat4mt
Same
Dbl: 4M-long m
Penalty
Other After PenX force thru 2¥
Vs 2N opening 34=Majors
```

### NOTRUMP OPENING BIDS

Fields this section feeds:

- [ ] `open.nt (by seat and vulnerability)` (compiled; default [{"hcp": [15, 17], "seats": [1, 2, 3, 4], "vul": "any"}])
- [ ] `open.nt_five_major` (compiled; default true)
- [ ] `open.nt_six_minor` (compiled; default false)
- [ ] `resp.nt` (compiled; default {"stayman": true, "transfers": "jacoby", "texas": true, "two_spade": "clubs", "super_accept": true})
- [ ] `resp.nt.puppet_stayman` (recorded only)
- [ ] `resp.nt.smolen` (recorded only)
- [ ] `resp.nt.three_level` (recorded only)
- [ ] `resp.nt.system_on_over_x` (recorded only)
- [ ] `comp.lebensohl` (recorded only)
- [ ] `open.two_nt` (compiled; default [20, 21])
- [ ] `open.three_nt` (compiled; default {"type": "gambling"})

```
NOTRUMP OPENING BIDS
1
3% Xferto
14+ to 17
3@ 5-5m GF
to
3y 3-1-(5-4
5-card Majorcommon ll
3a 1-3-(5-4
System on over _X, 2c
24 StaymanMlPuppet)
2¢@ Transferto
1]
4, 44 Transfer ll
Forcing StaymanL)
Smolen
2¢ Transferto a
Lebensoh| i
low denies)
Neg. Double i:
2NT Puppet Stayman
Other: Mod. Baze
```

### SIMPLE OVERCALL

Fields this section feeds:

- [ ] `comp.overcall_1` (compiled; default [8, 16])
- [ ] `comp.overcall_2` (compiled; default [11, 16])
- [ ] `comp.overcall_len` (compiled; default 5)

```
SIMPLE OVERCALL
1 level
8
to__16 HCP (usually)
often 4 cardsC) very light style
Responses
New Suit: Forcing NFConstil™ NFO
Jump Raise: Forcing Inv. Weakil
S=F1, Jump Cue= MR. Xfer/Dbl
```

### JUMP OVERCALL

Fields this section feeds:

- [ ] `comp.jump_overcall` (compiled; default "weak")

```
JUMP OVERCALL
Strong
Intermediate] Weak
Respond as if we opened
```

### OVER OPP'S T/O DOUBLE

```
OVER OPP'S T/O DOUBLE
New SuitForcing: 1 level12 level
Jump Shift: Forcing OInv. Weak
2a Size ore
Redouble implies no fit)
2NT Over
Limit+ Limit
Weak
Majors
ti
a
Minors
Oo
Other 3M-Lor3m=!
ixed. JSom:
```

### OPENING PREEMPTS

Fields this section feeds:

- [ ] `open.three_level` (compiled; default {"len": 7, "hcp_max": 10})
- [ ] `open.four_level` (compiled; default {"len": 8, "hcp_max": 12})
- [ ] `open.weak_quality` (not in _fields.json: check card.py DEFAULTS)
- [ ] `open.weak_top3` (compiled)
- [ ] variants: statements of seat, vulnerability or strength (style list; variants where a field holds them)

```
OPENING PREEMPTS
Sound
Light Very Light
3/4-bids
Oo
o
o
Conv/Resp. 44 PKC (4¢/#)
```

### MAJOR OPENING

Fields this section feeds:

- [ ] `open.major_len (1st/2nd and 3rd/4th)` (compiled; default 5)
- [ ] `resp.one_nt_to_major` (compiled; default "forcing")
- [ ] `resp.single_raise` (compiled; default [6, 10])
- [ ] `resp.limit_raise` (compiled; default [10, 12])
- [ ] `resp.major_jump_raise` (not in _fields.json: check card.py DEFAULTS)
- [ ] `resp.major_2nt` (compiled; default "jacoby")
- [ ] `resp.jacoby_min` (not in _fields.json: check card.py DEFAULTS)
- [ ] `resp.splinters` (compiled; default true)
- [ ] `resp.major.drury` (recorded only)
- [ ] `resp.major.bergen` (recorded only)
- [ ] `resp.major.3nt_raise` (recorded only)

```
MAJOR OPENING
Expected Min. Length
4
5
‘tst/2nd
Oo
1]
3rd/4th
1]
o
RESPONSES
Double Raise: ForceC] Inv. Weak i
After Overcall: ForceC] Inv.) Weak ll
Conv. Raise: 2NTM 3NTMM Splinter
Other: 1v-3@ & 1a-3N are mini spl.
INT: Forcing = Semi-forcing
2NT: Forcing Inv. Mod tdlacoby
to.
Drury: Reversi
i
2-WayC) Fit
3
Inv.
Other: 34 =
LR. 3M-1 Mixed in coi
22 to
+
i+
Strong] Other
2¢@ Resp: NegD
5
to__10 HCP
—s_t
5
to_10 HCP
5
```

### MINOR OPENING

Fields this section feeds:

- [ ] `open.minor` (compiled; default {"1C_min": 3, "1D_min": 3, "with_33": "1C", "with_44": "1D"})
- [ ] `resp.inverted_minors` (compiled; default false)
- [ ] `resp.minor_2nt` (compiled; default [11, 12])
- [ ] `resp.minor_3nt` (compiled; default [13, 15])
- [ ] `resp.minor.criss_cross` (recorded only)
- [ ] `resp.minor.walsh` (recorded only)

```
MINOR OPENING
Expected Min. Length 4 3 0-2 Conv.
le
Omo oo
1¢@
geo
RESPONSES
Double Raise: Force
Inv. Weak ll
After Overcall: Force]
Inv. Weak i
Forcing Raise: J/S in other minor
Single raise Other: 2@=LR
Frequently bypass 4+
INT/1 oe
6
to,
10
2NT Forcing
Inv.
nl
to_12-
3NT:
12+
to,
15
Other 1¢-34 Nat Inv
RESPONSES/REBIDS
Ogust, 44 PKC
2NT Force ll New Suit NFL
Ogust, 44 PKC
2NT Force ll New Suit NFL
Ogust, 44 PKC
2NT Forcelll New Suit NFL
```

### DIRECT CUEBID

Fields this section feeds:

- [ ] `comp.michaels` (compiled; default true)
- [ ] `comp.michaels_major_min` (not in _fields.json: check card.py DEFAULTS)

```
DIRECT CUEBID
OVER:
Minor
Major
Natural
o
o
Strong T/O0
o
o
_ 5ayo0=55
Michaels
( ( ) 2 =(54)2 @=55 _
Im-IN)or(1#-1¢
```

### VS Opening Preempts

Fields this section feeds:

- [ ] `comp.vs_preempts` (recorded only)

```
VS Opening Preempts Double Is
Takeout thru _4¥
Penalty
Cony. Takeout: Leaping Michaels
Lebensohl 2NT Response lll
Other: (2)-3 ¢=Majors
ANT: Blackwood i RKC 1430
cific kins
PKC.
e
SN Pick. 5N Quant. Non-Serious 3N.
3NT:
Level:
>5v
RoPILD
```

### SLAM CONVENTIONS

Fields this section feeds:

- [ ] `slam` (compiled; default {"blackwood": "rkc1430", "gerber": true})
- [ ] `slam.vs_interference` (recorded only)
- [ ] `slam.exclusion` (recorded only)
- [ ] `slam.kickback` (recorded only)
- [ ] `slam.cuebid_style` (recorded only)

```
SLAM CONVENTIONS Gerberlll
0314 if ask is NOT 4N. Redwood-usually a jump. Sp
Exclusion. 4N TO may be slam t
vs Interference OOPI
DEPOm
```

### LEADS

Fields this section feeds:

- [ ] `carding.length_lead_vs_suit`: one of 4th, 3rd_5th, attitude
- [ ] `carding.length_lead_vs_nt`: one of 4th, 3rd_5th, attitude
- [ ] `carding.lead_from_ak`: one of ace, king
- [ ] `carding.honor_sequence_lead`: one of top, rusinow
- [ ] `carding.three_small_lead_vs_suit`: one of top, low, middle
- [ ] `carding.three_small_lead_vs_nt`: one of top, low, middle
- [ ] `carding.four_small_lead`: one of 4th, second

```
LEADS (circle card led, if not in bold)
versus Suits _
versus Notrump.
XX X(
xx
xx
xx
XX X(
XXX
BKx
T9x
AQJx
JX
KQx
KJTx
AJT9
AT9x
aux
KT9x
(KQJx
IT 9
K(
JT9
Qatgx
QJTx
Qt9x
KQT9
JT9x
xX
>)
LENGTH LEADS:
4th Best
vs SUITS vs NT
3rd/5th Best
vs SUITS vs NTO
K from AKx 5 level+ or attitude vs NTC
shifting to singleton
Primary signal to partner's leads
Attitude il
Count) Suit preference
Last modified: Jun 27 2026 00:25
```

### DEFENSIVE CARDING

Fields this section feeds:

- [ ] `carding.attitude`: one of standard, upside_down
- [ ] `carding.count`: one of standard, upside_down
- [ ] `carding.signal_on_partner_lead`: one of attitude, count, suit_preference
- [ ] `carding.signal_on_declarer_lead`: one of count, suit_preference, none

```
DEFENSIVE CARDING
vs SUITS vs NT
Standard:
o
oO
Except
J
Qe
Vs Suits: SP if stiff in
dummy or equivalent
Upside-Down:
2
count
a
a
attitude
1]
1]
```

### DESCRIBE

Fields this section feeds:

- [ ] `open.strong_2c` (compiled; default {"hcp": 22, "ltc": 3, "ltc_hcp": 17})
- [ ] `resp.strong_2c` (compiled; default {"waiting": "2D", "positive_min": 8})
- [ ] `open.two` (compiled; default {"2D": {"type": "weak", "hcp": [5, 10], "len": [6, 6]}, "2H": {"type": "weak", "hcp": [5, 10], "len": [6, 6]}, "2S": {"type": "weak", "hcp": [5, 10], "len": [6, 6]}})
- [ ] `resp.weak_two_2nt` (compiled; default "feature")
- [ ] `open.weak_quality` (not in _fields.json: check card.py DEFAULTS)

```
DESCRIBE
HCP
After o'call
ModKokish
Waiting ll P=values X=wedk2.@-34=2nd neg
Natural: Weak Intermediate“) StrongL Conv.
Xfer over doubl
Natural: Weak Intermediate“) Strong Conv.
10 _ HCP
Xfer over doubl
Natural: Weak Intermediate“) StrongX Conv.
```

### FIRST DISCARD

Fields this section feeds:

- [ ] `carding.first_discard`: one of attitude, lavinthal, odd_even, count

```
FIRST DISCARD
Lavinthal
Odd/Even
```

### OTHER CONV. CALLS

Fields this section feeds:

- [ ] `rebid.new_minor_forcing` (recorded only)
- [ ] `rebid.fourth_suit_forcing` (recorded only)
- [ ] `resp.minor.weak_jump_shifts` (recorded only)

```
OTHER CONV. CALLS: New Minor Forcing:
2-Way NMF i
Weak Jump Shifts: In Comp. Not in Comp. Ml 1¥-2@ 1m-2 red Preempt
4th Suit Forcing: 1 Rd.
Gamelll_U vs U when both suits known
Mod Wolff 2N_rebid, Mathe vs big club.
After we open 1M and they overcall, 2N = LR 4+, cue = LR 3+. Xfer/Dbl
Ist seat favorable at IMPS 3x opening very light - Jxxxxx and out possible
```

### OTHER CARDING

Fields this section feeds:

- [ ] `carding.smith_echo`: one of none, standard, reverse
- [ ] `carding.trump_signal`: one of none, suit_preference, count

```
OTHER CARDING
Smith Echo
Trump Suit Pref.
Foster Echo
SPECIAL CARDING (1 PLEASE ASK
```

## Style statements found

Each becomes a field, a variant (by seat and vulnerability), "the defaults hold", or a `not_placed` line with the reason.

- (card) 4H Maximal
- (card) Balancing: 11 to 1406
- (card) Jumpto2NT: Minors) 2Lowestlll
- (card) Conv.-] Balancing 2N=19-21
- (card) Card-showingM™ Min.
- (card) VERY LIGHT: Openings)
- (card) 3rd Handl)
- (card) Wk min <14
- (card) often 4 cardsC) very light style
- (card) minor(s) Slam try
- (card) K Ist-3rd
- (card) MINOR OPENING
- (card) Light Very Light
- (card) Expected Min.
- (card) Expected Min.
- (card) ‘tst/2nd
- (card) 3rd/4th
- (card) Forcing Raise: J/S in other minor
- (card) Other: 1v-3@ & 1a-3N are mini spl.
- (card) Waiting ll P=values X=wedk2.@-34=2nd neg
- (card) 4th Best
- (card) 3rd/5th Best
- (card) CALLS: New Minor Forcing:
- (card) 4th Suit Forcing: 1 Rd.
- (card) Ist seat favorable at IMPS 3x opening very light - Jxxxxx and out possible

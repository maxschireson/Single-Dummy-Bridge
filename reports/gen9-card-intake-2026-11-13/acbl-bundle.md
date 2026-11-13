# Card intake bundle: sample-a-acbl

Made by `scripts/gen9_card_intake.py v0 (G9-B8)` on 2026-11-13 09:52 UTC. Procedure: docs/gen9/card-intake.md.
Layout guessed: **acbl** (signature headings found: {'acbl': 4, 'wbf': 0}).

Read every field against the page images; the text below is an aid. Suit symbols: taken from the text layer (symbol-font codes decoded) where it kept them; check each against the image.

## Pages

- `pages/acbl-sample-a-redacted-p1.png` from `samples/cards/acbl-sample-a-redacted.pdf` page 1: 384 lines, pdf text layer

## acbl-sample-a-redacted.pdf p1

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
Negative
thru
4H
Responsive
: thru
Maximal
2x-1
Support: Dbl.
thru
Redbl
Card-showing
Min. Offshape T/O
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
NAMES
15
18
Direct:
to
Systems on
Sandwich by PH only
Conv.
11
14(16)
Balancing:
to
Jump to 2NT: Minors
2 Lowest
Balancing 2N=19-21
Conv.
```

### (before any heading)

```
-
VERY LIGHT: Openings
FORCING OPENING: 1♣
21
to
Transfer Responses:
Texas
Pup to 3N with
ling
to
No outside A-K 1st-3rd
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
5-card M, 2/1 GF. Frequently respond with <6 HCP.
Two Over One: Game Forcing
Game Forcing ExceptWhen Suit Rebid
3rd Hand
Overcalls
Preempts
2♣
Natural 2 Bids
Other
20
2NT
Puppet Stayman
Jacoby
3♠
minor(s) Slam try
Gamb
3NT
XX forces 2♣/Pen X
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
Majors
Same
2♣
One major
Same
2♦
14+
5♥ + m
Same
2♥
5♠+4m+
Same
2♠
4M-long m
Penalty
Dbl:
After PenX force thru 2♥
Other
Vs 2N opening 3♣=Majors
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
1NT
Xfer to ♦
3♣
17
to
5-5m GF
3♦
to
3-1-(5-4)
3♥
5-card Major common
1-3-(5-4)
X, 2c
3♠
System on over
2♣Stayman
Puppet
2♦Transfer to ♥
4♦, 4♥Transfer
Forcing Stayman
Smolen
slow
2♥Transfer to ♠
Lebensohl
(
denies)
Size or♣
Neg. Double
:
Puppet Stayman
Mod. Baze
Other:
```

### SIMPLE OVERCALL

Fields this section feeds:

- [ ] `comp.overcall_1` (compiled; default [8, 16])
- [ ] `comp.overcall_2` (compiled; default [11, 16])
- [ ] `comp.overcall_len` (compiled; default 5)

```
SIMPLE OVERCALL
8
16
1 level
to
HCP (usually)
often 4 cards
very light style
Responses
New Suit: Forcing
NFConst
NF
Jump Raise: Forcing
Inv.
Weak
JS=F1, Jump Cue= MR. Xfer/Dbl
```

### JUMP OVERCALL

Fields this section feeds:

- [ ] `comp.jump_overcall` (compiled; default "weak")

```
JUMP OVERCALL
Strong
Intermediate
Weak
Respond as if we opened
```

### OVER OPP'S T/O DOUBLE

```
OVER OPP'S T/O DOUBLE
New Suit Forcing:1 level
2 level
2♠
Jump Shift:Forcing
Inv.
Weak
2NT
Redouble implies no fit
2NT Over
Limit+
Limit
Weak
Majors
Minors
3M-1or3m=Mixed. JSom=inv+
Other
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
Light
Very Light
3/4-bids
4♣ PKC (4♦/♣)
Conv./Resp.
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
1st/2nd
3rd/4th
RESPONSES
Double Raise: Force
Inv.
Weak
After Overcall: Force
Inv.
Weak
Conv. Raise: 2NT
3NT
Splinter
1♥-3♠ & 1♠-3N are mini spl.
1NT: Forcing
Semi-forcing
Mod
Jacoby
2NT: Forcing
Inv.
to
to
: Reverse
2-Way
Fit
1M-3♣, 1♠-3♥ Inv.
3♦ = LR. 3M-1 Mixed in comp.
22
+
to
Strong
Other
2♦Resp: Neg
5
10
to
Natural: Weak
Intermediate
5
10
to
Natural: Weak
Intermediate
5
10
to
Natural: Weak
Intermediate
Weak Jump Shifts: In Comp.
4th Suit Forcing: 1 Rd.
Mod Wolff 2N rebid, Mathe vs big club,
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
NF
Expected Min. Length 4
3 0–2 Conv.
1♣
1♦
RESPONSES
Double Raise: Force
Inv.
Weak
After Overcall: Force
Inv.
Weak
Forcing Raise: J/S in other minor
2♠ = LR
Single raise
Other:
Frequently bypass 4+♦
6
10
1NT/1♣
to
11
12-
2NT Forcing
Inv.
to
12+
15
3NT:
to
1♦-3♣ Nat Inv
Other
RESPONSES/REBIDS
Ogust, 4♣ PKC
New Suit NF
New Suit NF
New Suit NF
1♥-2♠ 1m-2 red Preemptive.
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
Strong T/O
Michaels
(1m-1N)or(1♣-1♦) 2♣=(54)2♦=55
SLAM CONVENTIONS Gerber
vs Interference: DOPI
DEPO
LEADS (circle card led, if not in bold)
versus Suits
versus Notrump
x x
x x x x
x x
x x x
x x x x x x x x
A K x
T 9 x
A K J x
K Q x
K J T x
A J T 9
Q J x
K T 9 x
K Q J x
J T 9
Q T 9 x
Q J T x
K Q T 9
J T 9 x
LENGTH LEADS:
4th Best
vs SUITS
3rd/5th Best
vs SUITS
K from AKx 5 level+ or
Attitude vs NT
shifting to singleton
Primary signal to partner's leads
Attitude
Count
Suit preference
SPECIAL CARDING
Last modified: Jun 27 2026 00:25
```

### VS Opening Preempts

Fields this section feeds:

- [ ] `comp.vs_preempts` (recorded only)

```
VS Opening Preempts Double Is
4♥
Takeout
thru
Penalty
Leaping Michaels
Conv. Takeout:
Lebensohl 2NT Response
(2♦)-3♦=Majors
Other:
Other:
:
4NT: Blackwood
RKC
1430
0314 if ask is NOT 4N. Redwood-usually a jump. Specific kings. PKC.
Exclusion. 4N TO may be slam try, 5N Pick. 5N Quant. Non-Serious 3N.
3NT:
>5♥
Level:
ROPI
Drury
Other:
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
x x x x
Except
2♣
x x x x x
Vs Suits: SP if stiff in
A Q J x
dummy or equivalent
A T 9 x
2♦
Upside-Down:
K Q T 9
count
Q T 9 x
attitude
2♥
T 9 x x
2♠
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
P=values X=weak 2♠-3♣=2nd neg
Waiting
HCP
Strong
Conv.
2NT Force
Xfer over double Ogust, 4♣ PKC
HCP
Strong
Conv.
2NT Force
Xfer over double Ogust, 4♣ PKC
HCP
2NT Force
Strong
Conv.
OTHER CONV. CALLS: New Minor Forcing:
2-Way NMF
Not in Comp.
U vs U when both suits known
Game
After we open 1M and they overcall, 2N = LR 4+, cue = LR 3+. Xfer/Dbl
1st seat favorable at IMPS 3x opening very light - Jxxxxx and out possible
```

### FIRST DISCARD

Fields this section feeds:

- [ ] `carding.first_discard`: one of attitude, lavinthal, odd_even, count

```
FIRST DISCARD
Lavinthal
Odd/Even
vs NT
vs NT
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
PLEASE ASK
```

### Tick boxes

A box follows its label on ACBL-style cards: the label is the word just left of the box.

| Ticked | Colour | Label | Words before it | Header above | Box |
| --- | --- | --- | --- | --- | --- |
| ☐ | red (alert) | Penalty | Overcall: | DOUBLES | [104.4, 194.7, 110.2, 200.5] |
| ■ | black | Negative |  | Overcall: | [56.3, 206.7, 62.1, 212.5] |
| ■ | black | Responsive |  | thru | [65.1, 218.7, 70.9, 224.5] |
| ■ | red (alert) | Dbl. | Support: | : | [72.4, 230.7, 78.3, 236.5] |
| ■ | red (alert) | Redbl | thru 2x-1 | Maximal | [144.6, 230.7, 150.5, 236.5] |
| ■ | black | Card-showing |  | Dbl. | [73.7, 242.7, 79.6, 248.5] |
| ☐ | black | cards | often 4 | to | [75.5, 293.9, 81.3, 299.7] |
| ☐ | black | style | very light | (usually) | [138.3, 293.9, 144.2, 299.7] |
| ☐ | black | Forcing | New Suit: | Responses | [91.7, 314.7, 97.5, 320.5] |
| ■ | black | NFConst | Forcing | style | [131.1, 314.7, 136.9, 320.5] |
| ☐ | black | Forcing | Jump Raise: | NFConst | [101.0, 324.7, 106.9, 330.5] |
| ☐ | black | Inv. | Raise: Forcing | NFConst | [124.5, 324.7, 130.3, 330.5] |
| ☐ | red (alert) | Strong |  | JS=F1, | [49.3, 365.7, 55.2, 371.5] |
| ☐ | red (alert) | Intermediate |  | OVERCALL | [110.6, 365.7, 116.5, 371.5] |
| ■ | black | Weak | Intermediate | Xfer/Dbl | [148.7, 365.7, 154.5, 371.5] |
| ☐ | black | 3/4-bids |  | Sound | [79.1, 415.7, 84.9, 421.5] |
| ☐ | black | 3/4-bids |  | Light | [109.6, 415.7, 115.4, 421.5] |
| ☐ | black |  |  | Light | [146.1, 415.7, 151.9, 421.5] |
| ☐ | red (alert) | Natural |  | Minor | [95.6, 468.7, 101.5, 474.5] |
| ☐ | red (alert) |  |  | Major | [130.6, 468.7, 136.5, 474.5] |
| ☐ | black | T/O | Strong | Minor | [95.6, 478.7, 101.5, 484.5] |
| ☐ | black |  |  | Major | [130.6, 478.7, 136.5, 484.5] |
| ■ | black | Michaels |  | Minor | [95.6, 488.7, 101.5, 494.5] |
| ■ | black |  |  | Major | [130.6, 488.7, 136.5, 494.5] |
| ■ | black | Gerber | CONVENTIONS | 2♣=(54)2♦=55 | [146.3, 513.8, 152.2, 519.6] |
| ■ | black | DOPI | Interference: | may | [107.8, 546.8, 113.6, 552.6] |
| ■ | black | DEPO | DOPI | try, | [146.7, 546.8, 152.6, 552.6] |
| ■ | black | SUITS | vs | x | [134.0, 686.6, 139.9, 692.4] |
| ☐ | black | SUITS | Best vs | SUITS | [134.0, 697.6, 139.9, 703.4] |
| ■ | black | Attitude |  | Primary | [58.3, 737.1, 64.1, 742.9] |
| ☐ | black | Count | Attitude | to | [97.7, 737.1, 103.6, 742.9] |
| ■ | black | on | 18 Systems | OVERCALLS | [290.5, 195.8, 296.3, 201.6] |
| ☐ | red (alert) | Conv. |  | Direct: | [191.7, 206.8, 197.6, 212.6] |
| ■ | black | Maximal | thru 4H |  | [151.6, 218.7, 157.5, 224.5] |
| ☐ | black | Minors | to 2NT: | to | [245.8, 228.8, 251.6, 234.6] |
| ■ | black | Lowest | Minors 2 | on | [289.1, 228.8, 294.9, 234.6] |
| ☐ | red (alert) | Conv. | Offshape T/O | Jump | [191.7, 239.8, 197.6, 245.6] |
| ☐ | black | T/O | Min. Offshape |  | [153.4, 242.7, 159.3, 248.5] |
| ☐ | black | NF | NFConst | (usually) | [151.6, 314.7, 157.5, 320.5] |
| ■ | black | Weak | Forcing Inv. |  | [154.0, 324.7, 159.8, 330.5] |
| ☐ | black | level | Suit Forcing:1 | T/O | [251.4, 364.6, 257.2, 370.4] |
| ☐ | black | level | level 2 | DOUBLE | [280.3, 364.6, 286.2, 370.4] |
| ☐ | black | Shift:Forcing | Jump | Forcing:1 | [235.9, 375.9, 241.8, 381.7] |
| ☐ | black | Inv. | Shift:Forcing | 2 | [255.1, 375.9, 260.9, 381.7] |
| ■ | black | Weak | Shift:Forcing Inv. | level | [281.5, 375.9, 287.4, 381.7] |
| ☐ | black | fit | implies no | Inv. | [245.9, 387.2, 251.8, 393.0] |
| ■ | red (alert) | Majors |  | Limit+ | [228.8, 409.8, 234.6, 415.6] |
| ☐ | red (alert) |  |  | Limit | [255.8, 409.8, 261.6, 415.6] |
| ☐ | red (alert) |  |  | Weak | [280.5, 409.8, 286.4, 415.6] |
| ☐ | red (alert) | Minors |  | Limit+ | [228.8, 419.8, 234.6, 425.6] |
| ☐ | red (alert) |  |  | Limit | [255.8, 419.8, 261.6, 425.6] |
| ■ | red (alert) |  |  | Weak | [280.5, 419.8, 286.4, 425.6] |
| ■ | black | Takeout | Major | Opening | [199.5, 461.7, 205.4, 467.5] |
| ☐ | red (alert) | Penalty | 4♥ | Double | [285.6, 461.7, 291.4, 467.5] |
| ■ | red (alert) | Response | Lebensohl 2NT | Michaels | [262.0, 484.3, 267.9, 490.1] |
| ■ | black | Blackwood | 4NT: | (2♦)-3♦=Majors | [221.4, 513.8, 227.2, 519.6] |
| ■ | black | RKC | Blackwood | (2♦)-3♦=Majors | [251.2, 513.8, 257.1, 519.6] |
| ■ | black | 1430 | RKC | Michaels | [285.0, 513.8, 290.8, 519.6] |
| ☐ | black | ROPI | >5♥ | 3N. | [289.5, 546.8, 295.3, 552.6] |
| ☐ | black | Standard: |  | SUITS | [260.7, 583.4, 266.6, 589.3] |
| ☐ | black |  |  | vs | [286.7, 583.4, 292.6, 589.3] |
| ☐ | black | Except |  | DEFENSIVE | [225.6, 593.2, 231.5, 599.1] |
| ■ | black | count |  | equivalent | [261.3, 637.4, 267.2, 643.3] |
| ■ | black | count |  |  | [287.3, 637.4, 293.2, 643.3] |
| ■ | black | attitude |  | equivalent | [261.3, 647.2, 267.2, 653.1] |
| ■ | black | attitude |  |  | [287.3, 647.2, 293.2, 653.1] |
| ☐ | black | Lavinthal |  |  | [260.7, 676.6, 266.6, 682.5] |
| ☐ | black |  |  |  | [287.3, 676.6, 293.2, 682.5] |
| ☐ | black | Odd/Even |  |  | [260.7, 686.4, 266.6, 692.3] |
| ☐ | black |  |  |  | [287.3, 686.4, 293.2, 692.3] |
| ■ | black | NT | SUITS vs | x | [170.0, 686.6, 175.9, 692.4] |
| ☐ | black |  |  |  | [260.7, 696.2, 266.6, 702.1] |
| ☐ | black |  |  |  | [287.3, 696.2, 293.2, 702.1] |
| ☐ | black | NT | SUITS vs | NT | [170.0, 697.6, 175.9, 703.4] |
| ☐ | black | NT | Attitude vs | NT | [170.0, 708.6, 175.9, 714.4] |
| ☐ | black | Echo | Smith |  | [260.7, 717.8, 266.6, 723.7] |
| ☐ | black |  |  |  | [287.3, 717.8, 293.2, 723.7] |
| ■ | black | Pref. | Trump Suit |  | [260.7, 727.6, 266.6, 733.5] |
| ☐ | black | preference | Suit | leads | [165.9, 737.1, 171.7, 742.9] |
| ☐ | black | Echo | Foster |  | [260.7, 737.4, 266.6, 743.3] |
| ☐ | black |  |  |  | [287.3, 737.4, 293.2, 743.3] |
| ☐ | black | CARDING |  | Foster | [179.1, 752.0, 187.0, 759.8] |
| ☐ | black | Forcing | One: Game | Frequently | [412.4, 234.3, 418.3, 240.2] |
| ☐ | black | Openings | VERY LIGHT: | Game | [387.6, 244.6, 393.5, 250.5] |
| ☐ | black | Hand | Openings 3rd | Game | [440.3, 244.6, 446.2, 250.5] |
| ☐ | red (alert) | 1♣ | FORCING OPENING: | Forcing | [392.4, 254.9, 398.2, 260.8] |
| ■ | black | 2♣ | OPENING: 1♣ | 3rd | [420.2, 254.9, 426.0, 260.8] |
| ■ | black | common | 5-card Major | NOTRUMP | [381.4, 312.3, 387.3, 318.1] |
| ■ | black | 2♣Stayman |  | X, | [353.3, 333.3, 359.1, 339.1] |
| ☐ | black | Puppet | 2♣Stayman |  | [384.9, 333.3, 390.7, 339.1] |
| ■ | blue (announce) | ♥ | 2♦Transfer to | Puppet | [368.0, 343.8, 373.9, 349.6] |
| ☐ | red (alert) | Stayman | Forcing | Puppet | [378.8, 354.3, 384.7, 360.1] |
| ■ | red (alert) | Smolen | Stayman | 4♥Transfer | [423.5, 355.4, 429.3, 361.2] |
| ■ | blue (announce) | ♠ | 2♥Transfer to | Stayman | [368.0, 364.8, 373.9, 370.6] |
| ■ | red (alert) | Lebensohl |  | 4♥Transfer | [432.5, 365.8, 438.3, 371.6] |
| ■ | black | Double | Neg. | slow | [441.1, 376.2, 446.9, 382.0] |
| ☐ | black |  |  | 4 | [399.2, 431.2, 405.0, 437.0] |
| ■ | black |  |  | 5 | [421.2, 431.2, 427.0, 437.0] |
| ■ | black |  |  | 4 | [399.2, 443.2, 405.0, 449.0] |
| ☐ | black |  |  | 5 | [421.2, 443.2, 427.0, 449.0] |
| ☐ | black | Force | Double Raise: | RESPONSES | [376.4, 467.2, 382.2, 473.0] |
| ■ | black | Inv. | Raise: Force | RESPONSES | [398.6, 467.2, 404.5, 473.0] |
| ■ | red (alert) | Weak | Force Inv. |  | [428.2, 467.2, 434.0, 473.0] |
| ☐ | black | Force | After Overcall: | Inv. | [380.8, 479.2, 386.7, 485.0] |
| ☐ | black | Inv. | Overcall: Force | Weak | [403.1, 479.2, 408.9, 485.0] |
| ■ | black | Weak | Force Inv. |  | [432.6, 479.2, 438.4, 485.0] |
| ■ | red (alert) | 2NT | Conv. Raise: | Force | [369.7, 491.2, 375.6, 497.0] |
| ■ | red (alert) | 3NT | Raise: 2NT | Inv. | [394.9, 491.2, 400.8, 497.0] |
| ■ | red (alert) | Splinter | 3NT | Weak | [431.5, 491.2, 437.4, 497.0] |
| ■ | blue (announce) | Forcing | 1NT: | 1♥-3♠ | [353.5, 515.2, 359.4, 521.0] |
| ☐ | blue (announce) | Semi-forcing |  | mini | [411.9, 515.2, 417.8, 521.0] |
| ☐ | black | Forcing | 2NT: | Forcing | [353.3, 527.2, 359.2, 533.0] |
| ☐ | black | Inv. | 2NT: Forcing | Semi-forcing | [375.6, 527.2, 381.4, 533.0] |
| ■ | red (alert) | Drury | ROPI | Forcing | [327.2, 551.2, 333.0, 557.0] |
| ■ | red (alert) | Reverse | Drury : | to | [368.8, 551.2, 374.7, 557.0] |
| ☐ | red (alert) | 2-Way | Reverse | Mod | [402.0, 551.2, 407.9, 557.0] |
| ■ | red (alert) | Fit | Reverse 2-Way | Jacoby | [421.5, 551.2, 427.4, 557.0] |
| ☐ | black | Strong |  | to | [356.4, 601.8, 362.2, 607.7] |
| ☐ | red (alert) | Other | Strong | HCP | [391.8, 601.8, 397.6, 607.7] |
| ☐ | black | Neg | 2♦Resp: | Other | [375.3, 612.6, 381.2, 618.4] |
| ■ | black | Waiting | Neg | After | [419.6, 612.6, 425.4, 618.4] |
| ■ | black | Weak | Natural: | to | [357.0, 639.0, 362.9, 644.9] |
| ☐ | red (alert) | Intermediate | Weak | HCP | [405.6, 639.0, 411.5, 644.9] |
| ☐ | red (alert) | Strong | Intermediate | P=values | [438.8, 639.0, 444.6, 644.9] |
| ■ | black | Weak | Natural: | to | [357.0, 664.4, 362.9, 670.3] |
| ☐ | red (alert) | Intermediate | Weak | HCP | [405.6, 664.4, 411.5, 670.3] |
| ☐ | red (alert) | Strong | Intermediate | Xfer | [438.8, 664.4, 444.6, 670.3] |
| ■ | black | Weak | Natural: | to | [357.0, 691.8, 362.9, 697.7] |
| ☐ | red (alert) | Intermediate | Weak | HCP | [405.6, 691.8, 411.5, 697.7] |
| ☐ | red (alert) | Strong | Intermediate | Xfer | [438.8, 691.8, 444.6, 697.7] |
| ■ | black | Comp. | Shifts: In | CALLS: | [405.9, 718.0, 411.8, 723.9] |
| ☐ | red (alert) | Rd. | Forcing: 1 | Comp. | [385.0, 730.0, 390.8, 735.9] |
| ■ | red (alert) | Game | 1 Rd. | Not | [414.9, 730.0, 420.8, 735.9] |
| ☐ | black | Rebid | ExceptWhen Suit |  | [549.6, 234.3, 555.5, 240.2] |
| ☐ | black | Overcalls | Hand | ExceptWhen | [490.5, 244.6, 496.3, 250.5] |
| ☐ | black | Preempts | Overcalls | Rebid | [542.0, 244.6, 547.9, 250.5] |
| ☐ | red (alert) | Bids | Natural 2 | Overcalls | [480.0, 254.9, 485.8, 260.8] |
| ☐ | red (alert) | Other | 2 Bids | Preempts | [513.2, 254.9, 519.0, 260.8] |
| ☐ | black | Stayman | Puppet | 21 | [559.6, 287.4, 565.4, 293.2] |
| ■ | blue (announce) | Jacoby |  | Responses: | [529.9, 307.0, 535.8, 312.8] |
| ■ | blue (announce) | Texas | Jacoby | Responses: | [568.3, 307.0, 574.2, 312.8] |
| ■ | blue (announce) | 4♥Transfer | 4♦, |  | [461.2, 345.0, 467.1, 350.8] |
| ☐ | black |  |  | 4 | [530.4, 430.8, 536.3, 436.7] |
| ■ | black |  |  | 3 | [543.4, 430.8, 549.3, 436.7] |
| ☐ | blue (announce) |  |  | 0–2 | [556.4, 430.8, 562.3, 436.7] |
| ☐ | red (alert) |  |  | Conv. | [574.8, 430.8, 580.7, 436.7] |
| ■ | black |  |  | 4 | [530.4, 442.8, 536.3, 448.7] |
| ■ | black |  |  | 3 | [543.4, 442.8, 549.3, 448.7] |
| ☐ | blue (announce) |  |  | 0–2 | [556.4, 442.8, 562.3, 448.7] |
| ☐ | red (alert) |  |  | Conv. | [574.8, 442.8, 580.7, 448.7] |
| ☐ | black | Force | Double Raise: | RESPONSES | [516.8, 466.8, 522.7, 472.7] |
| ■ | black | Inv. | Raise: Force | RESPONSES | [542.6, 466.8, 548.4, 472.7] |
| ■ | red (alert) | Weak | Force Inv. |  | [572.9, 466.8, 578.7, 472.7] |
| ☐ | black | Force | After Overcall: | Inv. | [523.1, 478.8, 528.9, 484.7] |
| ■ | black | Inv. | Overcall: Force | Weak | [548.8, 478.8, 554.6, 484.7] |
| ■ | black | Weak | Force Inv. |  | [579.1, 478.8, 584.9, 484.7] |
| ☐ | red (alert) | minor | in other | Weak | [570.3, 490.8, 576.1, 496.7] |
| ■ | red (alert) | raise | spl. Single | Raise: | [492.4, 502.8, 498.3, 508.7] |
| ■ | black | 4+♦ | Frequently bypass | 2♠ | [536.5, 514.8, 542.3, 520.7] |
| ☐ | black | Forcing | 2NT | 6 | [494.4, 538.8, 500.2, 544.7] |
| ☐ | black | Inv. | 2NT Forcing | to | [520.9, 538.8, 526.7, 544.7] |
| ☐ | red (alert) | Conv. | Strong | X=weak | [470.3, 639.0, 476.2, 644.9] |
| ■ | black | Force | Conv. 2NT | 4♣ | [524.2, 640.1, 530.0, 645.9] |
| ☐ | red (alert) | NF | New Suit |  | [576.4, 640.1, 582.2, 645.9] |
| ☐ | red (alert) | Conv. | Strong | double | [470.3, 664.4, 476.2, 670.3] |
| ■ | black | Force | Conv. 2NT | 4♣ | [524.2, 664.8, 530.0, 670.6] |
| ☐ | red (alert) | NF | New Suit | NF | [576.4, 664.8, 582.2, 670.6] |
| ■ | black | Force | Conv. 2NT | 4♣ | [524.2, 691.2, 530.0, 697.1] |
| ☐ | red (alert) | NF | New Suit | NF | [576.4, 691.2, 582.2, 697.1] |
| ☐ | red (alert) | Conv. | Strong | double | [470.3, 691.8, 476.2, 697.7] |
| ☐ | red (alert) | Forcing: | New Minor | double | [477.8, 706.0, 483.7, 711.9] |
| ■ | red (alert) | NMF | Forcing: 2-Way | New | [533.4, 706.0, 539.2, 711.9] |
| ■ | red (alert) | Comp. | Not in | Forcing: | [468.1, 718.0, 474.0, 723.9] |

## Style statements found

Each becomes a field, a variant (by seat and vulnerability), "the defaults hold", or a `not_placed` line with the reason.

- (card) Balancing:
- (card) Maximal
- (card) Jump to 2NT: Minors
- (card) Balancing 2N=19-21
- (card) VERY LIGHT: Openings
- (card) 3rd Hand
- (card) Wk min <14
- (card) very light style
- (card) minor(s) Slam try
- (card) No outside A-K 1st-3rd
- (card) MINOR OPENING
- (card) Very Light
- (card) Expected Min.
- (card) Expected Min.
- (card) 1st/2nd
- (card) 3rd/4th
- (card) Forcing Raise: J/S in other minor
- (card) 1♥-3♠ & 1♠-3N are mini spl.
- (card) P=values X=weak 2♠-3♣=2nd neg
- (card) 4th Best
- (card) 3rd/5th Best
- (card) CALLS: New Minor Forcing:
- (card) 4th Suit Forcing: 1 Rd.
- (card) 1st seat favorable at IMPS 3x opening very light - Jxxxxx and out possible
- (notes) Open most balanced hands non-vul with 12 HCP, but could pass a bad one vul.
- (notes) Open balanced 11 usually only NV and only if especially good (aces, tens).
- (notes) Unbalanced hands loosely follow the rule of 20, but use judgment based on honor location, spots, , vul, and likely rebid problems.
- (notes) 3rd seat can open light, especially if you want that lead
- (notes) Frequently respond light to opening bid, esp non vul
- (notes) 6-card m is possible, but never ‘too good’ a hand.
- (notes) 2-level opening should be 6-card suit in 1st/2nd.
- (notes) “Good suit” = 2 of top 3.
- (notes) “Good hand” = 8-10.
- (notes) Fourth seat 2-level opening shows a maximum weak 2 bid - definitely less than a solid 1-level opening
- (notes) 3-level opening should be a 7-card suit with 4-6 playing tricks if non-vul, and 6-7 playing tricks if vul.
- (notes) At imps, we play 1st seat FAVORABLE preempt can be VERY light – almost any hand with a 6-card suit would ‘qualify’.
- (notes) Do not preempt if your hand is too good (even if partner is a PH) or has too many ‘flaws’, such as good playability in side majors (especially spades) or too much stuff in your short suits.
- (notes) Gambling 3NT: no outside A or K if 1st-3rd seat.
- (notes) 1N overcall is a good 15-18 HCP.
- (notes) Fourth seat (sandwich) NT is 15-18 HCP.
- (notes) Balancing 1N is 11-14 vs. 1m; 11-16 vs. 1M.
- (notes) Balancing JUMP 2N overcall is 19-21 HCP.
- (notes) Balancing double then 1N (or non-jump to 2N) is 15-18 HCP (17-18 after 1M)
- (notes) Overcalls are wide range – 7-17 HCP.
- (notes) Balancing jump overcall is INTERMEDIATE – about an opening bid with 6-card suit
- (notes) Balancing double can be a king light
- (notes) Balancing double can be a king light

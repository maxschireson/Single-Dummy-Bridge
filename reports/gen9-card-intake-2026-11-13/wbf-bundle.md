# Card intake bundle: sample-a-wbf

Made by `scripts/gen9_card_intake.py v0 (G9-B8)` on 2026-11-13 09:52 UTC. Procedure: docs/gen9/card-intake.md.
Layout guessed: **wbf** (signature headings found: {'acbl': 1, 'wbf': 3}).

Read every field against the page images; the text below is an aid. Suit symbols: taken from the text layer (symbol-font codes decoded) where it kept them; check each against the image.

## Pages

- `pages/wbf-sample-a-redacted-p1.png` from `samples/cards/wbf-sample-a-redacted.pdf` page 1: 143 lines, pdf text layer
- `pages/wbf-sample-a-redacted-p2.png` from `samples/cards/wbf-sample-a-redacted.pdf` page 2: 122 lines, pdf text layer

## wbf-sample-a-redacted.pdf p1

### (before any heading)

```
DEFENSIVE AND COMPETITIVE BIDDING
B
W B F CONVENTION CARD
ot
CATEGORY: Green:
NCBO: USA
PLAYERS:
–
EVENT Rosenblum
2/1 FG.
```

### LEADS

Fields this section feeds:

- [ ] `carding.lead_from_ak`: one of ace, king
- [ ] `carding.honor_sequence_lead`: one of top, rusinow
- [ ] `carding.three_small_lead_vs_suit`: one of top, low, middle
- [ ] `carding.three_small_lead_vs_nt`: one of top, low, middle
- [ ] `carding.four_small_lead`: one of 4th, second

```
LEADS AND SIGNALS
In Partner’s Suit
If raised, high from xxx(x)
xxS unless raised
Same
LEADS
Lead
Ace
King
Queen
Jack
10
9
Hi-X
Lo-X
```

### OVERCALLS

Fields this section feeds:

- [ ] `comp.overcall_1` (compiled; default [8, 16])
- [ ] `comp.overcall_2` (compiled; default [11, 16])
- [ ] `comp.overcall_len` (compiled; default 5)
- [ ] style: statements of seat, vulnerability or strength (style list; variants where a field holds them)

```
OVERCALLS (Style: Responses: 1 / 2 Level; Reopening)
LD is important. Wide Range. New suit NF
NV 4th seat overcall can be light
Jump Q = MIXED.. 2N is 4-card limit/1M if RHO acted or by PH
Resp. or Snapdragon DBL = No guarantees
XFER over Dbl. of 1M overcall from 1N to 2M-1
```

### OPENING LEADS STYLE

Fields this section feeds:

- [ ] `carding.length_lead_vs_suit`: one of 4th, 3rd_5th, attitude
- [ ] `carding.length_lead_vs_nt`: one of 4th, 3rd_5th, attitude

```
OPENING LEADS STYLE
h
Lead
m
Suit
4th best from any
aj
NT
4th best from honor
o
Subseq
Attitude
rs
Other:
Vs. Suit
KQ(x)
QJ(x)
J10(x), KJ10(x)
109(x), 10x, H109x
9x,
Sx, xxS, xxxS(x)
HxS, HxxS(x)
```

### 1NT OVERCALL

Fields this section feeds:

- [ ] `comp.nt_overcall` (compiled; default [15, 18])
- [ ] `comp.balancing_nt` (compiled; default [11, 14])
- [ ] `comp.balancing_nt_major` (compiled)

```
1NT OVERCALL (2nd/4th Live; Responses; Reopening)
15+-18, 2nd/4th LIVE. SOUND. System-On.
Re-opening 11-15
```

### SYSTEM SUMMARY

Fields this section feeds:

- [ ] `open.major_len` (compiled; default 5)
- [ ] `resp.two_over_one` (compiled; default "gf")
- [ ] `open.nt` (compiled; default [{"hcp": [15, 17], "seats": [1, 2, 3, 4], "vul": "any"}])
- [ ] style: statements of seat, vulnerability or strength (style list; variants where a field holds them)

```
SYSTEM SUMMARY
GENERAL APPROACH AND STYLE
5-CARD MAJORS (F 1NT).
MAY PASS BAL. 12 HCP VUL.
RESPOND VERY LIGHT
Most JUMP 3 New Suit RESP. INV.
FREQUENT USE OF NON-PENALTY DBL. IN COMP
1N = 14+-17
```

### VS. NT

Fields this section feeds:

- [ ] `comp.vs_nt` (compiled; default "natural")
- [ ] `comp.vs_nt_double` (compiled; default "penalty")

```
Vs. NT
AKx. K at 5+-level or sing. Asks unblock/count
AK or KQ
QJ, AQJ
J10, KJ10
109, H109
9xx
Sx, Sxx, SSxx(x)
HxS, HxxS(x)
Discarding
LO = ENC
LO = EVEN
SP
LO = ENC
VS. NT (vs. Strong/Weak; Reopening;PH)
LO = EVEN
DBL SNT = 4-card M + longer m. DBL WNT(13 poss) = PEN
SP
2♣ LANDY THEN 2♦ ADVANCE ASKS LONGER
2♦ = One M. 2M = M + m
Vs. 2N, 3♣ = LANDY, all else Natural
Vs. 3N, 4♣/♦ = Majors, better ,♥/♠
```

### JUMP OVERCALLS

Fields this section feeds:

- [ ] `comp.jump_overcall` (compiled; default "weak")
- [ ] `comp.unusual_2nt` (compiled; default true)

```
JUMP OVERCALLS (Style; Responses; Unusual NT)
PRE. .
2N = 2-lower unbid
Reopen: INTermediate
```

### SIGNALS IN ORDER OF PRIORITY

Fields this section feeds:

- [ ] `carding.attitude`: one of standard, upside_down
- [ ] `carding.count`: one of standard, upside_down
- [ ] `carding.signal_on_partner_lead`: one of attitude, count, suit_preference
- [ ] `carding.signal_on_declarer_lead`: one of count, suit_preference, none
- [ ] `carding.first_discard`: one of attitude, lavinthal, odd_even, count
- [ ] `carding.trump_signal`: one of none, suit_preference, count

```
SIGNALS IN ORDER OF PRIORITY
Partner’s Lead
Declarer’s Lead
1 LO = ENC
LO = EVEN
Suit 2 HI = EVEN
SP
3 SP (sing. In dummy) Informative
1 LO = ENC
LO = EVEN
NT 2 LO = EVEN
SP
3 SP
Signals (including Trumps):
Trump SP. SP vs. suits when no more tricks can be cashed or set up
Remainder Count – H/L = ODD.
DOUBLES
```

### DIRECT & JUMP CUE BIDS

Fields this section feeds:

- [ ] `comp.michaels` (compiled; default true)
- [ ] `comp.michaels_major_min` (not in _fields.json: check card.py DEFAULTS)

```
DIRECT & JUMP CUE BIDS (Style; Response; Reopen)
MICHAELS CUE 5(+)-5(+). 2N = GT. After 2M, 3♦ = GT in oM
(1M) 3M asks stopper. (1m)3m is Natural
```

### SPECIAL BIDS THAT MAY REQUIRE DEFENSE

Fields this section feeds:

- [ ] `resp.minor.weak_jump_shifts` (recorded only)
- [ ] `comp.vs_two_suiters` (recorded only)

```
SPECIAL BIDS THAT MAY REQUIRE DEFENSE
WJS responses of 2♦ or 2♥ or 1♥-2♠
1m-2♠ = INV. RAISE TO 3m
1st seat
MIXED RAISES
1m(1N)-2♣ = Both majors
(1♣-1♦ or 1m-1N) 2em = Both majors (2♦ = 5-5)
```

### VS.PREEMPTS

Fields this section feeds:

- [ ] `comp.vs_preempts` (recorded only)

```
VS.PREEMPTS (Doubles; Cue-bids; Jumps; NT Bids)
LEB AFTER UPH T/O DBL
LEAPING MICHAELS. 3M CUE ASKS STOPPER
SYSTEM ON AFTER 2N. CUE/JUMP CUE TO 4M = STRONG
MINORS
VS. ARTIFICIAL STRONG OPENINGS- i.e. 1♣ or 2♣
DBL = MAJORS, NT = Minors
1N and 2N usually “Cuebid’
OVER OPPONENTS’ TAKEOUT DOUBLE
Over 1m: JS in om = LR(+). 2N = PRE raise, 3m = Mixed Raise
Over 1M: XFER from 1N to 2M-1. Xfer can be for lead with fit
2N = LR. 3M-1 = MR. 3M = PRE. Other JS = PRE
```

### TAKEOUT DOUBLES

Fields this section feeds:

- [ ] `comp.takeout_double_min` (compiled; default 12)
- [ ] `comp.takeout_shape` (not in _fields.json: check card.py DEFAULTS)

```
TAKEOUT DOUBLES (Style; Responses; Reopening)
Sound. ELC. DBL of Preempt then new suit can be light.
SCRAMBLE 2N (3♥ over 2♠ instead is Game Try)
```

### SPECIAL FORCING PASS SEQUENCES

Fields this section feeds:

- [ ] `general.forcing_pass` (recorded only)

```
SPECIAL FORCING PASS SEQUENCES
Double of 1N overcall or WNT opening is forcing thru 2♥
```

### SPECIAL, ARTIFICIAL & COMPETITIVE DBLS/RDLS

Fields this section feeds:

- [ ] `comp.responsive_double_thru` (recorded only)
- [ ] `comp.support_double_thru` (recorded only)

```
SPECIAL, ARTIFICIAL & COMPETITIVE DBLS/RDLS
(1N-3N)X = LEAD WEAKER M
ACTION, STOLEN BID
LIGHTNER, BLIND SLAM. DBL OF 3N = LEAD MY BID SUIT
DBL OF 3N = DON’T LEAD YOUR PREEMPT SUIT
```

### IMPORTANT NOTES

Fields this section feeds:

- [ ] `general.psychs` (recorded only)

```
IMPORTANT NOTES
PEN PASS of RDBL at 3-level or higher or solo bidder
Split 2nd high under declarer
PSYCHICS:Rare
```


## wbf-sample-a-redacted.pdf p2

### (before any heading)

```
ARTIFICIAL
MIN. NO. OF
TICK IF
NEG.DBL
CARDS
THRU
COMPETITIVE & PASSED
DESCRIPTION
RESPONSES
SUBSEQUENT ACTION
HAND BIDDING
5♦
2♠ = LR 2♣ = GF. 1♦ COULD BE 3-CARD
3
CAN PASS BAL 12 HCP VUL
Bypass Major(s) with 1N rebid
PH Raise to 2m INV
WALSH. 3♣ = Mixed.
3
5♣
Only 3-card if 4-4-3-2
Same as over 1♣. 3♣ = INV.
Bypass ♠ with 1N rebid
Sound. Can be 4 NV in 3rd/4th
5
5♦
1N = F. 2m FG. 2♥ CONSTR. 2♠ = WJS
3♣ by PH INV.
2N = GF Raise. 3♣ = INV. 3♦ = LR. 3M = MR
REV DRURY WIDE RANGE
5
5♦
Same as 1♥
3♥ = INV/1♠. 2-tier SPL
4♦
4-SUIT JTB except 2♠ also Range Ask. Texas
15-17 5M POSS
2N = PUP STAY. 3♦ = 5-5m’s FG 3M = SPL
STRONG
2♦ = Waiting.
MOD. KOKISH 3m DBL NEG poss
3M Rebid is 4M + 5(+)♦
6
WEAK TWO
2N = Ogust, New suit = F
Might open 1 in 3rd
Sound Vul
WEAK TWO, Sound vul
2N = Ogust, New suit = F
Might open 1 in 3rd
6
WEAK TWO, Sound Vul
2N = Ogust, New suit = F
Might open 1 in 3rd
4♦
20-21
STAY, JTB, 3♠ PUP 3N, TEXAS
7(6)
Sound Vul. 1st NV vs. V ‘joke’
4♦ = PKC
Sound Vul. 1st NV vs. V ‘joke’
4♣ = PKC
7(6)
7(6)
Sound Vul. 1st NV vs. V ‘joke’
4♣ = PKC
Sound Vul. 1st NV vs. V ‘joke’
4♣ = PKC
7(6)
Solid minor. No A or K 1st-3rd
4♣ = P/C, 4♦ asks SPL
7
Aggressive NV
4♦ = PKC, 4N = Regular BLACK
7
Aggressive NV
4N = KC
7
Sound, not too good
4♠ = NAT, 4N = KC
7
Sound, not too good
4N = KC
Blackwood
8
8
8
8
NON-SERIOUS 3N
```

### OPENING

Fields this section feeds:

- [ ] `open.* by opening (rows 1C to 5S: min. cards, description)` (not in _fields.json: check card.py DEFAULTS)
- [ ] `resp.* (responses column)` (not in _fields.json: check card.py DEFAULTS)
- [ ] `comp.negative_double_thru (NEG.DBL THRU column)` (compiled; default "2S")
- [ ] variants (seat and vulnerability in the descriptions): statements of seat, vulnerability or strength (style list; variants where a field holds them)

```
OPENING
1♣
1♦
1♥
1♠
INT
2♣
ART
2♦
2♥
2♠
2NT
3♣
3♦
3♥
3♠
3NT
4♣
4♦
4♥
4♠
4NT
ART
5♣
5♦
5♥
5♠
```

### HIGH LEVEL BIDDING

Fields this section feeds:

- [ ] `slam` (compiled; default {"blackwood": "rkc1430", "gerber": true})
- [ ] `slam.exclusion` (recorded only)
- [ ] `slam.vs_interference` (recorded only)
- [ ] `slam.cuebid_style` (recorded only)

```
HIGH LEVEL BIDDING
SPLINTER BIDS. LAST TRAIN ST. JUMP TO 4N OFTEN QUANT.
RKCB 1430 (4N). OTHER KC 0314. EXCLUSION KC PREEMPT KC
REDWOOD IF A JUMP. OR AFTER NT OPENINGS
GERBER. ROMAN DOPI, DEPO
RELAY FOR SPL UP THE LINE
```

## Style statements found

Each becomes a field, a variant (by seat and vulnerability), "the defaults hold", or a `not_placed` line with the reason.

- (card) OVERCALLS (Style: Responses: 1 / 2 Level; Reopening)
- (card) Wide Range.
- (card) NV 4th seat overcall can be light
- (card) 4th best from any
- (card) 4th best from honor
- (card) 1NT OVERCALL (2nd/4th Live; Responses; Reopening)
- (card) 15+-18, 2nd/4th LIVE.
- (card) Re-opening 11-15
- (card) 12 HCP VUL.
- (card) RESPOND VERY LIGHT
- (card) 1st seat
- (card) NT (vs. Strong/Weak; Reopening;PH)
- (card) TAKEOUT DOUBLES (Style; Responses; Reopening)
- (card) DBL of Preempt then new suit can be light.
- (card) DBL = MAJORS, NT = Minors
- (card) Split 2nd high under declarer
- (card) CAN PASS BAL 12 HCP VUL
- (card) Can be 4 NV in 3rd/4th
- (card) REV DRURY WIDE RANGE
- (card) Might open 1 in 3rd
- (card) Sound Vul
- (card) WEAK TWO, Sound vul
- (card) Might open 1 in 3rd
- (card) WEAK TWO, Sound Vul
- (card) Might open 1 in 3rd
- (card) Sound Vul.
- (card) 1st NV vs. V ‘joke’
- (card) Sound Vul.
- (card) 1st NV vs. V ‘joke’
- (card) Sound Vul.
- (card) 1st NV vs. V ‘joke’
- (card) Sound Vul.
- (card) 1st NV vs. V ‘joke’
- (card) Solid minor.
- (card) No A or K 1st-3rd
- (card) Aggressive NV
- (card) Aggressive NV
- (card) Sound, not too good
- (card) Sound, not too good
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

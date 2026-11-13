# Card intake bundle: sample-a-wbf-photo

Made by `scripts/gen9_card_intake.py v0 (G9-B8)` on 2026-11-13 09:53 UTC. Procedure: docs/gen9/card-intake.md.
Layout guessed: **wbf** (signature headings found: {'acbl': 1, 'wbf': 3}).

Read every field against the page images; the text below is an aid. Suit symbols: none decoded; read every symbol-bearing field from the image.

OCR against the PDF text layer: 82.9% of the reference's 561 words of 3+ letters are in the OCR text.

## Pages

- `pages/wbf-sample-a-p1.png` from `samples/cards/wbf-sample-a-p1.png`: 147 lines, ocr (tesseract, psm 11), mean word confidence 81.5
- `pages/wbf-sample-a-p2.png` from `samples/cards/wbf-sample-a-p2.png`: 114 lines, ocr (tesseract, psm 11), mean word confidence 79.6

## wbf-sample-a-p1.png

### (before any heading)

```
DEFENSIVE AND COMPETITIVE BIDDING
B
WB F CONVENTION CARD
IOVERCALLS (Style: Responses: 1/2 Level; Reopening)
h
LD is important. Wide Range. New suit NF
ICATEGORY: Green:
NV 4* seat overcall can be light
™tSuit
INCBO: USA.
Jump Q = MIXED.. 2N is 4-card limit/1M if RHO acted or by PH
AUNT
PLAYERS: i A - i
c Subseq
Resp. or Snapdragon DBL = No guarantees
EVENT Rosenblum
IXFER over Dbl. of 1M overcall from
N to 2M-1
Other:
INT OVERCALL (2"4/4" Live; Responses; Reopening)
15+-18, 2°4/4" LIVE. SOUND. System-On.
Re-openin|
11-15
2/1 FG.
IN
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
lotlOPENING LEADS STYLE
Lead
In Partner’s Suit
4" best from any
If raised, high from xxxQ)
4" best from honor
IxxS unless raised
Attitude
Same
LEADS:
Lead
Vs. Suit
AKx. K at 5+-level or sin;
jAce
King
KQ@)
Queen
QI)
Jack
3100), KI10Gx)
10
109(x), 10x, H109x
9
9x,
|Hi-X
Sx, xxS, xxxS00)
|Lo-X
HxS, HxxS(x)
ISIGNALS IN ORDER OF PRIORITY
Partner’s Lead
Declarer’s Lead
1}LO = ENC
[LO = EVEN
Suit 2/HI
SVEN
SP.
3|SP (sing. In dummy)|Informative
1JLO = ENC
[LO = EVEN
NT 2|LO = EVEN
SP.
3/SP
Signals (including Trumps):
Trump SP. SP vs. suits when no more tricks can be cashed or set up
[Remainder Count — H/L = ODD.
DOUBLES
ITAKEOUT DOUBLES (Style; Responses; Reopening)
Sound. ELC. DBL of Preempt then new suit can be light.
SCRAMBLE 2N (3¥ over 24 instead is Game Try)
ISPECIAL, ARTIFICIAL & COMPETITIVE DBLS/RDLS
(1N-3N)X = LEAD WEAKER M
|ACTION, STOLEN BID
ILIGHTNER, BLIND SLAM. DBL OF 3N = LEAD MY BID SUIT
IDBL OF 3N = DON’T LEAD YOUR PREEMPT SUIT
```

### SYSTEM SUMMARY

Fields this section feeds:

- [ ] `open.major_len` (compiled; default 5)
- [ ] `resp.two_over_one` (compiled; default "gf")
- [ ] `open.nt` (compiled; default [{"hcp": [15, 17], "seats": [1, 2, 3, 4], "vul": "any"}])
- [ ] style: statements of seat, vulnerability or strength (style list; variants where a field holds them)

```
SYSTEM SUMMARY
IGENERAL APPROACH AND STYLE
5-CARD MAJORS (F INT).
IMAY PASS BAL.
2 HCP VUL.
RESPOND VERY LIGHT
Most JUMP 3 New Suit RESP. INV.
FREQUENT USE OF NON-PENALTY DBL. IN COMP
44-17
```

### VS. NT

Fields this section feeds:

- [ ] `comp.vs_nt` (compiled; default "natural")
- [ ] `comp.vs_nt_double` (compiled; default "penalty")

```
Vs. NT
|Asks unblock/count
[AK or KQ
QU, AQU
10, KJ10
09, H109
xx
Sx, Sxx, SSxxQ)
HxS, HxxS(x)
Discarding
LO =ENC
LO =EVEN
SP
LO =ENC
VS. NT (vs. Strong/Weak; Reopening;PH)
LO =EVEN
IDBL SN
4-card M + longer m. DBL WNT(13 poss) = PEN
SP
24 LANDY THEN 2¢ ADVANCE ASKS LONGER
2@ =One M. 2M=M+m
Vs. 2N, 34 = LANDY, all else Natural
Vs. 3N, 4&/¢@ = Majors, better ,v/@
1VS.PREEMPTS (Doubles; Cue-bids; Jumps; NT Bids)
LEB AFTER UPH T/O DBL
[LEAPING MICHAELS. 3M CUE ASKS STOPPER
ISYSTEM ON AFTER 2N. CUE/JUMP CUE TO 4M = STRONG.
MINORS.
IVS. ARTIFICIAL STRONG OPENINGS- i.e. 1@ or 2@
IDBL = MAJORS, NT = Minors
IN and 2N usually “Cuebid’
OVER OPPONENTS’ TAKEOUT DOUBLE
Over Im: JS in om = LRG). 2N = PRE raise, 3m = Mixed Raise
Over 1M: XFER from 1N to 2M-1. Xfer can be for lead with fit
2N = LR. 3M-
= MR. 3M=PRE. Other JS = PRE
```

### JUMP OVERCALLS

Fields this section feeds:

- [ ] `comp.jump_overcall` (compiled; default "weak")
- [ ] `comp.unusual_2nt` (compiled; default true)

```
JUMP OVERCALLS (Style; Responses; Unusual NT)
PRE.
j2N =
lower unbid
Reopen: INTermediate
[DIRECT & JUMP CUE BIDS (Style; Response; Reopen)
__ After 2M, 3¢ = GT in oM
IMICHAELS CUE 5(+)-5(+). 2N =
(IM) 3M asks stopper. (Im)3m is Natural
```

### SPECIAL BIDS THAT MAY REQUIRE DEFENSE

Fields this section feeds:

- [ ] `resp.minor.weak_jump_shifts` (recorded only)
- [ ] `comp.vs_two_suiters` (recorded only)

```
SPECIAL BIDS THAT MAY REQUIRE DEFENSE
WJS responses of 2¢ or 2¥ or 1¥-24
1m-24 = INV. RAISE TO 3m
1% seat
MIXED RAISES
1m(1N)-2# = Both majors
(14-14 or 1m-1N) 2em = Both majors (2 # = 5-5)
```

### SPECIAL FORCING PASS SEQUENCES

Fields this section feeds:

- [ ] `general.forcing_pass` (recorded only)

```
SPECIAL FORCING PASS SEQUENCES
Double of IN overcall or WNT opening is forcing thru 2¥
IPEN PASS of RDBL at 3-level or higher or solo bidder
```

### IMPORTANT NOTES

Fields this section feeds:

- [ ] `general.psychs` (recorded only)

```
IMPORTANT NOTES
Split 2" high under declarer
IPSYCHICS:Rare
```


## wbf-sample-a-p2.png

### (before any heading)

```
Para
COMPETITIVE & PASSED
Zs
Ux
DESCRIPTION
RESPONSES
SUBSEQUENT ACTION
e<
a=
HAND BIDDING
ZO
ae
CAN PASS BAL 12 HCP VUL
Bypass Major(s) with IN rebid
PH Raise to 2m INV
le
56
24 =LR 2s =GF.
¢@ COULD BE 3-CARD
WALSH. 3® = Mixed.
le
Sm
Only 3-card if 4-4-3-2
Same as over
3% =INV.
Bypass @ with IN rebid
lv
56
Sound. Can be 4 NV in 3"/4th
1N = F. 2m FG. 2¥ CONSTI
2a=WIS
3% by
PH INV.
2N = GF Raise. 3# = INV. 3¢@ =LR.3M=MR
REV DRURY WIDE RANGE
la
54
Same as 1¥
3¥ =INV/14._2-tier SPL
INT
de
15-17 5M POSS
4-SUIT JTB except 2@ also Range Ask. Texas
2N = PUP STAY. 3 = 5-5m’s FG 3M = SPL
26
ART
STRONG
2¢ = Waiting.
MOD. KOKISH 3m DBL NEG poss
3M Rebid is 4M + 5(+)@
2¢
6
WEAK TWO
2N = Ogust, New suit=F
Might open | in 3rd
Sound Vul
WEAK TWO, Sound vul
2N = Ogust, New suit=F
Might open | in 3rd
2v
24
6
WEAK TWO, Sound Vul
2N = Ogust, New suit=F
Might open | in 3rd
2NT
4e
20-2
STAY, JTB, 34 PUP 3N, TEXAS
3H
16)
Sound Vul. 1s NV vs. V ‘joke’
4¢ =PKC
76)
Sound Vul. 1s NV vs. V ‘joke’
36
4& = PKC
16)
Sound Vul. 1“ NV vs. V ‘joke’
3v
4& = PKC
34
76)
Sound Vul. 1“ NV vs. V ‘joke’
4& = PKC
3NT
Solid minor. No A or K 18-3rd
4# =P/C,4¢@ asks SPL
Aggressive NV
4am
4¢ =PKC, 4N = Regular BLACK
4e
Aggressive NV
4N=KC
4
Sound, not too good
44 = NAT, 4N=KC
Sound, not too good
4N=KC
4a
4NT
Blackwood
ART
Se
Se
Sv
Sa
NON-SERIOUS 3N
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
REDWOOD IF A JUMP. OR AFTER NT OPENING!
GERBER. ROMAN DOPI, DEPO
RELAY FOR SPL UP THE LINE
```

## Style statements found

Each becomes a field, a variant (by seat and vulnerability), "the defaults hold", or a `not_placed` line with the reason.

- (card) IOVERCALLS (Style: Responses: 1/2 Level; Reopening)
- (card) Wide Range.
- (card) NV 4* seat overcall can be light
- (card) INT OVERCALL (2"4/4" Live; Responses; Reopening)
- (card) 2 HCP VUL.
- (card) RESPOND VERY LIGHT
- (card) 1% seat
- (card) NT (vs. Strong/Weak; Reopening;PH)
- (card) ITAKEOUT DOUBLES (Style; Responses; Reopening)
- (card) DBL of Preempt then new suit can be light.
- (card) MINORS.
- (card) IDBL = MAJORS, NT = Minors
- (card) CAN PASS BAL 12 HCP VUL
- (card) Can be 4 NV in 3"/4th
- (card) REV DRURY WIDE RANGE
- (card) Might open | in 3rd
- (card) Sound Vul
- (card) WEAK TWO, Sound vul
- (card) Might open | in 3rd
- (card) WEAK TWO, Sound Vul
- (card) Might open | in 3rd
- (card) Sound Vul.
- (card) 1s NV vs. V ‘joke’
- (card) Sound Vul.
- (card) 1s NV vs. V ‘joke’
- (card) Sound Vul.
- (card) 1“ NV vs. V ‘joke’
- (card) Sound Vul.
- (card) 1“ NV vs. V ‘joke’
- (card) Solid minor.
- (card) No A or K 18-3rd
- (card) Aggressive NV
- (card) Aggressive NV
- (card) Sound, not too good
- (card) Sound, not too good

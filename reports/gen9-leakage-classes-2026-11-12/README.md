# E9-16 part 1b: what our equal-card habits give away, on p41's house pools

Gen 9 research (sam, signals) for g9's E9-16, 12 November 2026. Kind of evidence: **prediction** (double-dummy
tricks saved on stored solves; no match). Nothing adopted.

**Data.** p41's published pools (`transfer/gen8-p41-reading-pools-20261112`): 530 house tables, 21,417
decisions of every seat after the opening lead, 329 deals, every stored layout solved once. "A board" is p41's
unit: the four seats of one table. Standard errors by deal.

**Readings** (`scripts/gen9_reading_bench.py readings --class-reading`, on `8p-32`'s player, net v4, factor 1):

- `proto`: the net on the card, as the prototype reads (reproduces p41's stored v4 reading to 6e-6).
- `cls`: every hidden seat's play read by the net's probability of its class, the card inside chosen evenly. Class:
  the spots nine and below of the suit held (E9-3), or the card itself if higher.
- `tch`: the same with the class widened to the cards of the suit held that touch the card played, honours
  included (touching through cards already played).
- `clsopp`, `tchopp`: the opponents' plays read by class, partner's by the card; `clspar`, `tchpar`: the reverse.

On recorded tables a class reading is what a calibrated reader would gain against a version of us that chose
evenly inside the class, because it does not look at which equal card was played.

## Result

Tricks a board, paired against `proto` (the reading of the actual cards); the bench's own nats beside:

| What is read by class only | All decisions | Declarer deciding | Defender deciding |
| --- | ---: | ---: | ---: |
| Every hidden seat, spots | -0.038 ± 0.013 (-0.22 nats) | -0.023 ± 0.010 | -0.014 ± 0.008 |
| Every hidden seat, touching cards | -0.036 ± 0.017 (-0.21 nats) | -0.020 ± 0.013 | -0.016 ± 0.009 |
| The opponents' plays, spots | -0.028 ± 0.012 | -0.023 ± 0.010 | -0.005 ± 0.005 |
| The opponents' plays, touching | -0.021 ± 0.016 | -0.020 ± 0.013 | -0.001 ± 0.007 |
| Partner's plays, spots | -0.004 ± 0.007 | 0 | -0.004 ± 0.007 |
| Partner's plays, touching | -0.003 ± 0.006 | 0 | -0.003 ± 0.006 |

Against no reading, `proto` saves +0.185 ± 0.029 a board and `cls` +0.148 ± 0.028.

- Which of several equal spots the house bots play is worth 0.038 ± 0.013 tricks a board to a reader of our own
  strength, about a fifth of the whole reading.
- Most of it is our defenders' spots read by declarer: 0.023 ± 0.010. Our declarer's equal cards give the
  defenders 0.005 ± 0.005 (spots) or 0.001 ± 0.007 (touching cards).
- Our partner reads our defenders' spots for 0.004 ± 0.007. So choosing evenly among equal spots would take
  about 0.02 to 0.03 tricks a board from the opponents' reading and about 0.004 from our own.
- Widening the class to touching honours adds nothing measurable to the leak (-0.036 against -0.038).

**Limits.** The reader is the house net reading house bots, so this is the leak to a reader as good as ours, not
to BEN. Classes are by equality of rank, not by equality on the true deal; E9-3 found spots equal in 98.5% of
defender decisions. The house bots break exact ties by the net (`tie_break: net`), so these are the habits of that
rule.

# System-aware hand-fit scorer: first run on the house bidders (11 November 2026)

**A pipeline check, not a candidate.** Prediction validation only: the loss of the scorer's
"does this hand fit this seat's calls" classifier. No layout information in nats, no tricks,
no IMPs. The trained file is not released and no bot uses it.

## Question

Does the system layer ([docs/gen8_systems.md](../../docs/gen8_systems.md)) run end to end on
real bidders through the registry, and does the scorer use what is declared when the systems
are the three house bidders, which bid almost alike?

## Source, models, data

- Code: branch `feature/gen8-systems-20261111`.
- Systems and their pinned generators: `house-gen6` (`5b7ea255…`), `house-gen5` (`9ee52f3b…`),
  `house-dds40k` (`68047016…`). On 4,096 fresh deals the Gen 6 bidder's auctions differ from
  each of the other two on 26% of deals; Gen 5 and DDS-40k differ on 1.2%.
- Start: hand-fit scorer v0 (`56e64440…`, trained on 230,010 deals bid by the Gen 5 bidder).
  Its call table becomes the shared table; the three corrections start at zero.
- Training data: 18,000 random deals, 2,000 at each of the nine North-South/East-West
  pairings, seed 3100 (648,000 examples; `cef8837e…`). Validation: 2,700 deals, 300 per
  pairing, seed 9 (97,200 examples; `7056e663…`). The recipe for examples is the Gen 6
  scorer's: per seat the true hand, 3 random hands and 5 hands with 1-8 cards swapped, each
  labelled by replaying the seat's calls through its own side's bidder.

```bash
python scripts/gen_system_fit.py val.npz   --seed 9    --deals 2700  --systems house-gen6,house-gen5,house-dds40k
python scripts/gen_system_fit.py train.npz --seed 3100 --deals 18000 --systems house-gen6,house-gen5,house-dds40k
python scripts/train_system_scorer.py house3b.npz --steps 600 --lr 2e-4,2e-5 --val val.npz --train train.npz \
    --init models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz --report train_report.json
```

Generation ran at 230 to 280 deals per second on one core; training took 2.4 minutes on two
cores (600 steps of 1,024 examples, 0.95 passes). [Log](train_log.txt), [report](train_report.json).

## Results

Validation loss (lower is better). "Wrong" declares another of the three systems on purpose.

| North-South vs East-West | v0 as released | Declared | Hidden | Wrong |
| --- | ---: | ---: | ---: | ---: |
| Gen 6 vs Gen 6 | 0.1341 | 0.1240 | 0.1265 | 0.1295 |
| Gen 6 vs Gen 5 | 0.1148 | 0.1092 | 0.1107 | 0.1116 |
| Gen 6 vs DDS-40k | 0.1162 | 0.1111 | 0.1126 | 0.1162 |
| Gen 5 vs Gen 6 | 0.1394 | 0.1292 | 0.1315 | 0.1338 |
| Gen 5 vs Gen 5 | 0.1057 | 0.1059 | 0.1067 | 0.1052 |
| Gen 5 vs DDS-40k | 0.1159 | 0.1153 | 0.1161 | 0.1167 |
| DDS-40k vs Gen 6 | 0.1246 | 0.1174 | 0.1198 | 0.1241 |
| DDS-40k vs Gen 5 | 0.1123 | 0.1122 | 0.1126 | 0.1142 |
| DDS-40k vs DDS-40k | 0.1139 | 0.1132 | 0.1136 | 0.1165 |
| All | 0.1197 | 0.1153 | 0.1167 | 0.1186 |

Paired differences over all validation examples, standard errors clustered by deal:

| Difference | All tables | Tables with the Gen 6 bidder | Tables without it |
| --- | ---: | ---: | ---: |
| Declared - v0 | -0.0044 ± 0.0004 | -0.0076 ± 0.0006 | -0.0003 ± 0.0004 |
| Declared - hidden | -0.0014 ± 0.0002 | -0.0020 ± 0.0003 | -0.0006 ± 0.0002 |
| Wrong - declared | +0.0033 ± 0.0003 | +0.0048 ± 0.0005 | +0.0015 ± 0.0004 |

- v0 on this validation set gives 0.134 on Gen 6 auctions and 0.106 on Gen 5 auctions; its
  release notes give 0.138 and 0.112. The data path here reproduces the original recipe.
- The gain over v0 is where the Gen 6 bidder is at the table, as expected of a scorer trained
  on Gen 5 auctions. The v1a retrain on 460,387 Gen 6 deals reports 0.121 on Gen 6 auctions
  (its own validation deals); this run reaches 0.124 there from 18,000 mixed deals while
  leaving Gen 5 tables where they were.
- The declaration is used: hiding it costs a little and a wrong one costs more. The effects
  are small because the systems are nearly the same. Gen 5 against Gen 5 with a "wrong"
  declaration is not worse, since the wrong system there is DDS-40k.

## A run that failed, kept for the record

The first attempt ran 2,500 steps at learning rate 5e-4 to 5e-5, about four passes over the
18,000 deals. Validation loss fell for the first hundred steps and then rose steadily, from
0.124 to 0.139 on the examples logged; the final per-table losses were 0.124 to 0.154, worse
than v0. 18,000 deals support about one pass at this width. The trainer now ends at its best
validated state, the starting state included.

## Limits

- One run, one seed. The checkpoint was chosen on the validation deals that are reported
  (the curve was monotone and the last step was kept).
- 300 validation deals per pairing.
- Three bidders from one lineage. Nothing here says how the scorer does on a system that
  differs in kind; no such system has a generator yet.
- In the v1a study a loss change of this size on Gen 6 auctions (0.138 to 0.121) moved the
  deal list's information by 0.021 ± 0.012 nats per decision, and its trick value was not
  measured. Nothing at the table was measured here either.

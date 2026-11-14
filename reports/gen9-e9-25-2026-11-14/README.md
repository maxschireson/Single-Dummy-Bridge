# E9-25: conditional claims at 0.9 against BEN defenders, scorer weights against Gen 9's

g9, 14 Nov 2026. Registration: `team/gen9:experiments/E9-25.md`, from E9-24's post-hoc result on Precision defenders
(committed lines failed 8.7% of the time with the scorer's weights and 3.5% with Gen 9's;
`reports/gen9-sid-weights-2026-11-13`).

**Not confirmed as registered.** Where BEN 64 defends, lines committed at a floor of 0.9 failed 8 of 160 times with
the scorer's weights (5.0% +- 1.7) and 5 of 165 times with Gen 9's (3.0% +- 1.3). That is E9-24's direction, but this
sample cannot tell it from no difference. Prediction (1) is met on the point estimate only; (2) and (3) are not met.
Conditional claims are already off by default in X9 (G9-A11), so this changes no play setting.

## Predictions

| Registered prediction | Result | Verdict |
| --- | --- | --- |
| (1) Committed lines fail at least 1.5 times as often with the scorer's weights as with Gen 9's | ratio 1.65, 95% interval 0.55 to 4.94 | met on the point estimate; the interval includes 1 |
| (2) Where only one weighting commits, the scorer-only lines cover the actual layout less often than the Gen 9-only lines, p below 0.05 | scorer-only lines cover 4 of 6, Gen 9-only 10 of 11: Fisher one-sided p = 0.27. Where both commit (154 positions), only Gen 9 covers 3 and only the scorer 1: McNemar exact p = 0.625 | not met |
| (3) Gen 9's failure rate is within 3 points of the house-defended control's | 3.0% against 10.0% (10 of 100): -7.0 +- 3.3 points | not met |

Errors are one standard error unless an interval is given.

## Slices (registered)

Committed lines that fail, BEN defending:

| Slice | Scorer | Gen 9 |
| --- | --- | --- |
| 8 cards | 4 of 89 | 4 of 91 |
| 7 cards | 4 of 71 | 1 of 74 |
| Partscores | 4 of 86 | 4 of 89 |
| Games | 2 of 65 | 1 of 67 |
| Slams | 0 of 4 | 0 of 4 |
| Doubled | 2 of 5 | 0 of 5 |
| Games, slams and doubled | 4 of 74 | 1 of 76 |

The difference between the weightings is all in games, slams and doubled contracts; on partscores they fail equally.

## What differs between the two weightings

- **Only BEN's seats.** Gen 9 reads BEN's calls by replaying BEN's own bidding net (`ReplayReader`); the scorer reads
  them as house calls. With BEN defending, the median effective number of layouts is 721 with the scorer's weights
  and 563 with Gen 9's, and the best card differs on 39 of 835 positions. With house bots defending, Gen 9's reading
  is the scorer, so the two columns are identical (the best card differs on 0 of 742).
- **The control is the other side of the same tables.** In the BEN-defended positions `8s-32` declares and BEN 64
  defends; in the house-defended ones BEN 64 declares and `8s-32` defends. So (3) compares different declarers and
  contracts as well as different defenders. The control's failures include 2 of 3 slams and 2 of 3 doubled contracts.

## Run

- Box job `e9-25` on azure4 (owner g9), source `feature/gen9` at `adae5fbb`, 14 Nov 09:08 to 09:15 UTC: one pass, as
  the stopping rule says. The first start (02:47 UTC) failed loading BEN's net; `adae5fbb` fixed the loader (BEN saves
  its output layer inside TimeDistributed).
- Results: transfer branch `transfer/gen9-e9-25-azure4-20261114` at `c3033825` (never merged into source).
- BEN's net: `GIB-BBO-8742_2026-10-23-E30.keras`, SHA-256 `b0dff3df…`. The scorer: the Gen 8 feeds'
  `artifacts/gen6/scorer.npz`, SHA-256 `56e6444079d1…`.
- The analysis is `experiments/e9_25/e925_report.py`, committed at `9bb9aed` on 13 Nov, before the run.

## Population and deviations

- **Positions.** 2,730 native tables with BEN 64 in `arena-gen8-azure3-ben64-1-feed` to `-8-feed` gave 5,124 positions:
  1,330 and 1,312 with BEN defending at 8 and 7 cards, 1,255 and 1,227 with house bots defending. The first 750 of each
  were studied, which is the registered cap of 1,500 per population. Of those, 835 BEN-defended and 742 house-defended
  positions had no outright claim; they are the population.
- **Deviation 1, feeds.** The registration names "arena-gen8-\*-ben64-\* and BEN 16 feeds". There are no Gen 8 BEN 16
  feed branches, and the job read only the first BEN 64 family, not the `-f-` and `-p2-` families. The cap was reached
  from the first family, so the others would have changed which positions were used, not how many.
- **Deviation 2, the test for (2).** The registration names McNemar's test on discordant pairs for positions where only
  one weighting commits, and those are not pairs. The report script gives both readings, Fisher's exact test on the two
  groups and McNemar's test where both commit; neither reaches p below 0.05.

## Files

| File | What |
| --- | --- |
| `report.txt` | The box's output of `e925_report.py` |
| `slices.txt`, `e925_slices.py` | The registered slices and the weight summaries above, with the report script's definitions |
| `ben_defends-8.jsonl.gz`, `ben_defends-7.jsonl.gz`, `house_defends-8.jsonl.gz`, `house_defends-7.jsonl.gz` | One line per position: weights, cells, floors and certified sets for both weightings |
| `positions.log`, `job.json` | The positions step's count and the box job's spec |

To reproduce from the four files, unzipped into a folder `DIR`:

```
python3 experiments/e9_25/e925_report.py DIR
python3 reports/gen9-e9-25-2026-11-14/e925_slices.py DIR
```

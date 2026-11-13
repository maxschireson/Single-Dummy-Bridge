Ladder: 8p-32 and the five x8 Gen 8 variants are on the live chart (08:31); E9-21 adopted, E9-20 rejected (as worded)

will, 13 Nov 08:31 UTC. Reply to 20261113T0756Z-g9-ladder-max-asked-via-g7-07-22.

**Ladder** (gh-pages b1d2f293, fit 08:31, 121 feeds, 68,997 boards):
- **8p-32:** a point since dave's eed2f575: Gen 8, parent 8s-32, prior 0 ± 0.05, +0.67, hollow.
- **The five variants:** candidates in configs/ladder-bots.json on feature/gen9-ladder (I wrote these entries in dave's file; I am telling him), group 'Gen 8 variant (box match)' in Gen 8's colour. Figures are from x8's 07:45 board entry, placed on 8s-32 because x8 measured against 8p-32-v41, the same search as 8s-32:

| Variant | x8's figure (boards) | On the ladder |
| --- | ---: | ---: |
| 8x1-ft1 | +0.30 ± 0.15 (522) | +0.95 |
| 8xr0-ft1 | −0.07 ± 0.14 (246) | +0.58 |
| 8x3-ft1 | +0.08 ± 0.08 (1,011) | +0.73 |
| 8x2-ft1 | −0.15 ± 0.12 (550) | +0.50 |
| 8z-ft1 | −0.38 ± 0.14 (541) | +0.27 |

- **Caveat on each drill-down:** these are common-auction (card-play) figures; the ladder's points are native.
- **Layout:** candidates now get their own lane right of the fit time, so they no longer cover 9a-32 and 8p-32.

**Verdicts:**
- **E9-21: adopted** as a method (Nash average beside the field score). I reproduced it with your script on my 08:25 rows: t2 0.0066, the same orders, the equilibrium 8s-32 alone, SE ratio 1.09. Prediction (3) failed, which means the Nash average is precise enough to use. One new thing: with 9a-32's BEN-pair rows in, 9a-32 took the equilibrium in 1 of 50 replicates.
- **E9-20: rejected** as the hypothesis is worded: no member is redundant. Your design consequence (the three-distance rule, with behaviour counted on value-changing choices) stands. You proposed 'adopted' for that rule, so reopen if you read the labels the other way. On 2 shards I reproduced 8c-32 = 8s-32 on 0 of 12,197 decisions and 71s-32 against 8s-32 at 9.1%. The closest different pair (5-32 against 5R32) came out at 5.7% rather than 6.8%, which matters if the threshold sits near 5 to 7%.
- **E9-24:** from 09:21.

# Opening-lead attribution: original Gen5 and RZ coverage

Checked 2026-11-10. Positive IMPs favor the 192-sample bot.

## Direct RZ192–RZ32 coverage

Neither published RZ cohort schedules or reports a direct 5RZ192 versus 5RZ32 pair:
- arena-gen5rz-feed at 03fd90e694d02ba139559fc323e63e384da9e969: 151 records; RZ32 versus R32, and R192 versus BEN.
- arena-gen5rz-ben-feed at d35abf50a31cd5fd6971a6d42d9e634ffc87090b (18:56:49 UTC): 1,222 records; RZ32 versus R32, and RZ192 versus BEN. The 192/32 internal control remains R32 versus R192, not RZ.

Bot manifest thresholds verify the distinction: RZ near_tie=0, R near_tie=0.125. The preceding 147-board 5R opening-lead analysis must not be described as RZ evidence. No new match was launched.

## Original Gen5/192 versus Gen5/32

Combined two completed published cohorts:
- 231647b297ba7b05ee28e720d7f395bacbcff818: 954 paired boards, +214 IMP.
- 759365035cddadd6b5586bd8f10995aff40d9be3: 18 paired boards, -8 IMP.

Verified no shared deal families; the complete bot specifications/identities are identical across cohorts. In these manifests the key '5' means 192 samples. Both variants use near_tie=0.125 and identical promoted gen5 network hashes. Used common-auction root tables only, checked identical auctions/contracts/declarers across tables, recomputed all IMP signs from scores, and checked swapped partnership assignments. Native bidding is identical in this pair and is not counted again.

Combined: 972 distinct deals, +206 IMP for 192, +0.211934 IMP/deal, standard error 0.113331. Total-equivalent SE 110.158 IMP, approximately 1.87 SE from zero. Suggestive, not a decisive strength result.

| Opening-lead agreement | Deals | IMP for Gen5/192 |
|---|---:|---:|
| Same physical opening card | 687 | +59 |
| Different opening cards | 284 | +147 |
| Passed out | 1 | 0 |

Different-lead boards show a larger descriptive gain, but both subsequent play and lead selection differ. This does not attribute 147 IMP causally to the lead.

## Measured time

Means over 971 played deals, seconds charged to each bot across both duplicate tables. Each bot makes 52 decisions per paired deal: one opening lead and 51 later plays. Timing records have no missing decisions, and their stage counts were checked.

| Stage | Gen5/32 | Gen5/192 |
|---|---:|---:|
| Opening lead | 0.7664 | 8.3423 |
| Later decisions | 2.1895 | 14.9471 |
| Total | 2.9559 | 23.2894 |

Opening lead is 35.82% of Gen5/192's time and 37.26% of the extra time over Gen5/32. Replacing only the lead with a 32-sample choice would arithmetically save 32.53% of Gen5/192's own time if subsequent costs stayed constant. This hybrid has not been run; changed leads may change later costs.

The R cohorts are different deals and source-time conditions, so cross-cohort absolute timing differences are not a controlled sampler comparison. The high-priority missing measurement is direct RZ192 versus RZ32 and, for lead attribution, 32-on-lead/192-later versus 192-throughout under otherwise matched settings.

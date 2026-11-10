# Exact-auction bidding replay cost

Measured 30 newly reached contracts in previously observed strain/declarer
combinations with frozen clean Gen3 cardplay (32 worlds): 116.07 seconds total,
3.87 seconds mean, 3.30 seconds median, 7.54 seconds 90th percentile, 8.28 seconds
maximum. About 6–7 minutes per 100 replays is a useful local planning estimate;
this sample is not a bound on harder deals.

The probe uses the unchanged validated 40k bidder, not a newly trained candidate.
Both actual historical rooms and alternate recorded auctions were checked.

| Additional work | Greedy probe: 199 deals, unique auctions | Sampled training: 256 deals / 512 rooms |
|---|---:|---:|
| Unobserved strain/declarer | 2 | 75 |
| New contract in known strain/declarer | 1 | 38 |
| Same contract, different auction | 2 | 29 |
| Total exact-auction replays needed | 5 | 142 |

The greedy probe's two rooms coincide; the five missing auctions need five
plays, not ten. At the measured average this is approximately 20 seconds total.
The earlier comparison against only each deal's first reference auction
overcounted missing work because some alternatives were already recorded.

In sampled training, new levels/doubles within known strain/declarer combinations
add about 2.5 minutes per 256 play-source deal pairs. Full auction matching adds
about 4.3 minutes beyond the strain-only approach. The six-candidate 2,048-pair
plan contains 6,144 play-source pairs; a naive extrapolation gives about one
additional hour for new contracts within known strains and another 45 minutes
for changed auction paths, before reuse across candidates. Total new play under
exact matching extrapolates to about 3.7 serial hours before cross-candidate cache
hits. Future bidders can change these rates; this is not a promised finish time.

Eight of the 30 new results fell outside the range of their previous same-strain
trick results. This is not a controlled estimate of the effect of contract change:
play seeds and sometimes the historical clean bot version also differ. Exact
auction matching is now used, including levels, doubles, declarer, public bidding,
oriented cards, dealer and vulnerability.

The exact six-way mix experiment is running from the validated 40k parent. The
first 256 pairs completed with every room scored; the candidates are not yet
fully trained or evaluated. There has been no promotion. The run uses bounded
processes and commits Adam/model checkpoints after every batch. Nine focused
refresh tests and eleven existing bidding/PPO tests passed; the unrelated live
DDS-table integration test was skipped because no new DDS tables are required.

See [the experiment recipe](../docs/bidding_clean_mixes.md) for exclusions, split
rules, mix selection, limitations, and restart commands.

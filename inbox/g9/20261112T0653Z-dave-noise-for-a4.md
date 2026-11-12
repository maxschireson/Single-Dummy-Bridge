For G9-A4: per-board noise in the published feeds is pair-specific (SD 2.45 to 4.5 IMPs) and heavy-tailed (kurtosis 5 to 18); one sigma for all pairs and a Gaussian test would both be off.

From dave, 12 Nov. Data: every record of the 62 registry sources (43,239 rows), dashboard counting
rules applied (snapshot cut-off, ben32 and accidental cohorts out, a family once per pair, earliest
wins): 43,031 boards. Common auction, IMPs a board from the first-named side. Script
`scripts/arena_feed_rows.py` on `feature/gen9-arena-sim` (pushing within the hour).

| Pair | Boards | Mean | SE | SD | Flat share | Kurtosis | Share with \|IMPs\| >= 10 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 7s-32~6-32 | 3,083 | +0.262 | 0.058 | 3.21 | 0.73 | 13.3 | 0.055 |
| 6-32~5RZ32 | 3,025 | +0.730 | 0.076 | 4.20 | 0.54 | 7.4 | 0.099 |
| 6-32~ben | 1,835 | -0.106 | 0.103 | 4.40 | 0.54 | 7.9 | 0.107 |
| 7s-32~1 | 1,319 | +2.238 | 0.125 | 4.53 | 0.40 | 5.4 | 0.133 |
| 7s-32~5RZ32 | 1,319 | +1.139 | 0.114 | 4.15 | 0.53 | 7.4 | 0.099 |
| 7s-32~ben | 1,274 | +0.095 | 0.119 | 4.24 | 0.55 | 8.6 | 0.086 |
| 6-32~6-256 | 1,133 | -0.134 | 0.104 | 3.51 | 0.69 | 12.6 | 0.064 |
| 6-32~1 | 756 | +1.671 | 0.165 | 4.52 | 0.43 | 6.0 | 0.120 |
| 7s-32~ben64 | 684 | +0.069 | 0.153 | 4.01 | 0.56 | 8.7 | 0.094 |
| 71s-32~7s-32 | 239 | -0.201 | 0.158 | 2.45 | 0.79 | 17.9 | 0.042 |

What I take from it for the statistics:
- **Variance per pair.** The SD falls as two bots get closer (more identical tables). A rating model
  with one noise level would overweight boards between similar bots by about (4.4/2.5)^2 = 3 times.
  Per-pair variance estimated from the pair's own boards (shrunk toward a common value when a pair
  has few) is what I will simulate unless A4 says otherwise.
- **Tails.** Most boards are flat and a few are slam or game swings. A test that assumes Gaussian
  increments needs checking under these tails; E9-5 will run every setting with Gaussian noise and
  with a bootstrap of these per-board values. A variance-adaptive bound (for example an empirical-
  Bernstein or a normal mixture on a running variance) is the kind of thing that would survive it.
- **Additivity looks roughly right** at a first glance: 7s~6 + 6~5RZ predicts 7s~5RZ = +0.99,
  observed +1.14 +- 0.11; 7s~6 + 6~1 predicts 7s~1 = +1.93, observed +2.24 +- 0.13 (about 1.4 sigma
  of the combined error). D3 will do this properly.

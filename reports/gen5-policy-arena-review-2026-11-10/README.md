# Review: is the Gen5 policy losing IMPs to PIMC?

The evidence supports a narrower concern: the original Gen5/32 policy loses
on recorded non-tie overrides of a PIMC maximum. It does not establish that the
policy loses overall. The newer Gen5R/32 cohort does not reproduce the negative
override result. These are local one-move comparisons, not IMPs per board from
a policy-on versus policy-off match.

## Sources and verification

Two disjoint arena cohorts were frozen before analysis:

| Feed | Frozen commit | Completed boards | Snapshot generated UTC |
|---|---|---:|---|
| Original Gen5 | `231647b297ba7b05ee28e720d7f395bacbcff818` | 6,607 | 2026-11-10 14:16:17 |
| Gen5R | `8f386190b57714f94c904c922cbcdf36ab7791a2` | 2,030 | 2026-11-10 16:42:46 |

All 8,637 compressed episode blobs were checked against their GitHub Git blob
SHAs, with no missing, extra, or repeated files. The two cohorts have no shared
canonical deal families. Across 312,625 audits, the analysis checked matching
pre-fork card histories, the actual forced alternative card, acting seat,
stored PIMC gaps against the global maximum of recorded legal-card estimates,
and recomputed IMP gains from the two final scores. This is a record-consistency
check, not a new DDS solve or a new full legal replay of every arena table.

Both cohorts use the same Gen5 policy, belief and bidding model hashes. Gen5R
changes sampling for large positions. Policy SHA-256:
`03e70a6f6021c8bed471dc9de53f462b0e991320ff4ad7734bcc20f54c5aff18`.
The manifests are included beside this report.

## What the audit actually compares

The manifests specify `5 -> 3`, `5-32 -> 3`, and `5R32/5R192 -> 3` audit
references. `ArenaPlayer` loads Gen3's **selector** and applies it to the same
PIMC details used by Gen5. It does not run a separate Gen3 belief/sampling pass.
`collect_board` plays the alternative first card and holds the continuation
players fixed. Gains are from the acting partnership's perspective.

Consequently, an arbitrary audit is Gen5-selector versus Gen3-selector, not
Gen5 versus pure PIMC. We can directly compare with a global PIMC-best card
where the recorded Gen3 choice has gap to best at most `1e-7`. A non-tie
override is a Gen5 choice whose gap exceeds `1e-7`. All values below use that
filter. Tie comparisons are against the PIMC-best card selected by Gen3,
not against a uniformly random PIMC tie-breaker.

This is a selected subset. On common-auction root trajectories, original
Gen5 has 18,211 non-tie overrides across its 32- and 192-sample variants. Only
7,700 have a Gen3 reference at the global PIMC maximum, and 3,474 were audited.
Gen3 agrees with Gen5's inferior-PIMC card on 7,830 overrides. Gen5R has 5,211
root overrides, 2,122 with a PIMC-best reference, and 977 such audits; Gen3
agrees with Gen5R on 2,239 overrides. Thus we cannot measure the value of
disabling the policy on every override from these records alone.

## Non-tie overrides

The primary view uses common-auction tables and root trajectories actually
played in the arena. Recursive audits visit additional positions reached after
a reference move and therefore have a different position distribution. All
standard errors cluster by canonical deal family; forks are not treated as
independent boards. Values are IMP per qualifying audited choice.

| Policy / scope | Comparisons | Deal families | Mean IMP | Cluster SE | 95% interval |
|---|---:|---:|---:|---:|---|
| Original Gen5/32, common-auction root | 2,796 | 2,186 | -0.09728 | 0.05835 | [-0.21164, +0.01708] |
| Original Gen5/32, all unique rooms and depths | 5,070 | 2,877 | -0.13294 | 0.04143 | [-0.21414, -0.05174] |
| Gen5R/32, common-auction root | 977 | 752 | +0.09621 | 0.09705 | [-0.09400, +0.28643] |
| Gen5R/32, all unique rooms and depths | 1,820 | 991 | +0.04121 | 0.06385 | [-0.08394, +0.16636] |

The original Gen5/32 negative result is 3.21 standard errors from zero when
recursive forks are included, but 1.67 on root trajectories alone. The
common-auction recursive-only estimate is -0.17870 (SE 0.05561). The root-only
trick loss is -0.03827 tricks per qualifying override (SE 0.01405); including
all depths it is -0.04320 (SE 0.01004).

The direction of original Gen5/32's weakness is therefore consistent across
root and recursive positions, while its strength of evidence in IMPs depends
on the scope. Gen5R's positive estimates are inconclusive. Comparing the two
cohorts does not prove the new sampler fixed the problem: these are different
deals and opponent mixtures, not paired sampler-only counterfactuals.

Original Gen5/192 also has no convincing override loss: common-root +0.05752
(SE 0.11958; 678 comparisons), all-depth -0.04404 (SE 0.07529; 1,249). There
are no candidate-side Gen5R/192 fork audits in this snapshot: its candidate
matches are against BEN, for which audits are disabled. Gen5R/192 appearing
as an opponent does not supply its own policy-control forks.

## Tie-breaking and aggregate selected comparisons

These figures include all unique rooms and audited depths. Every row is
conditional on the reference being a global PIMC maximum and the cards
differing. Agreement audits are omitted from this table, not counted as losses.

| Policy | Decision category | Comparisons | Mean IMP | Cluster SE | Sum of local IMP gains |
|---|---|---:|---:|---:|---:|
| Original Gen5/32 | Exact PIMC tie changes | 57,728 | +0.01057 | 0.00604 | +610 |
| Original Gen5/32 | Non-tie overrides | 5,070 | -0.13294 | 0.04143 | -674 |
| Original Gen5/32 | Both categories | 62,798 | -0.00102 | 0.00676 | -64 |
| Gen5R/32 | Exact PIMC tie changes | 20,800 | +0.00712 | 0.01038 | +148 |
| Gen5R/32 | Non-tie overrides | 1,820 | +0.04121 | 0.06385 | +75 |
| Gen5R/32 | Both categories | 22,620 | +0.00986 | 0.01120 | +223 |

Original Gen5/32's observed tie-breaking gains nearly offset its override
losses in this selected sample. The tie benefit alone is not decisive, and
the combined estimate is essentially zero. Root-only combined estimates are
also inconclusive: original Gen5/32 -0.00154 (SE 0.01287), Gen5R/32 +0.02888
(SE 0.02420). Summed local gains overlap along trajectories; they are not a
match score and cannot be divided by board count to estimate IMPs per board.

The complete Gen5-versus-Gen3 audit means are also inconclusive. On common-root
positions they are +0.00119 IMP (SE 0.00412) for original Gen5 across sample
budgets, and +0.01147 (SE 0.00822) for Gen5R/32. This does not make Gen3 a pure
PIMC control.

## Relation to the fresh 256-board test

The [fresh global-choice experiment](../gen6-ddsd-fresh-256-2026-11-10/README.md)
explicitly forked the global PIMC choice, Gen5 choice, and corrected-search
choice on an outcome-independent sample of decisions. It reported Gen5 minus
PIMC +0.09804 IMP per audited decision (SE 0.06060) on 255 played boards.
Gen5's 341 tie changes contributed +75 local IMPs; its 39 non-tie overrides
contributed zero IMPs and -9 tricks. That small override sample does not refute
the larger original-arena override loss. Nor does the positive but uncertain
aggregate establish a policy benefit. It used ordinary 32-world sampling,
Gen5 self-play, different audit weighting, and a random PIMC tie baseline.

## Assessment and next test

The defensible claim is that original Gen5/32's non-tie overrides are suspect,
with meaningful evidence of local harm in the broader fork sample. A claim
that the entire current policy is demonstrably losing IMPs to pure PIMC in the
arena goes beyond these data. No matched whole-agent policy-on/off arena
comparison was present in the reviewed feeds.

The clean next test is current Gen5R with three fixed choices on the same
sampled worlds: strict PIMC maximum, policy restricted to exact PIMC ties,
and policy with its current 0.125-trick window. Fork every distinct selected
choice at randomly chosen root decisions, including cases where Gen3 agrees
with Gen5. Then a paired whole-agent match can measure board impact. A negative
outcome-minus-PIMC residual alone is calibration error, not a counterfactual
loss attributable to choosing the policy's card.

No arena configuration or model was changed in this review.

## Reproduction

`scripts/review_gen5_policy_arena.py` streams a pinned GitHub source tarball,
without extracting archive paths, and writes audit rows, decision coverage,
episode provenance, manifests and clustered summaries. For each commit above,
download `https://codeload.github.com/maxschireson/Single-Dummy-Bridge/tar.gz/COMMIT`
and run the script with `--archive`, `--label gen5` or `gen5r`, `--commit`, and
`--output`. Optional `--blobs` accepts a JSON object with a `files` map from
episode basename to Git blob SHA. The episode tree SHAs used for verification
were `fb83ef95320bc316b3643b7d4293ea41f12000a5` and
`019e530cd1b5a7ce4bef709ba04d79b0b8f247a4`, respectively.

Machine-readable summaries retain both comparison-weighted means with
deal-clustered SEs and equal-family means with their SEs. The small depth
sensitivity file additionally filters common-auction non-tie rows by depth
and 32-sample candidate. Raw episodes remain in the pinned source feeds;
derived row files can be regenerated without training or running DDS.

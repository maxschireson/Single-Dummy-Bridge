Re cohort: azure4 has no drained run with unallocated deals; no BEN servers; families list not on the box

will, 13 Nov 04:54 UTC. Reply to 20261113T0446Z-dave-cohort-azure4-source-run-ben-s.

Read-only inventory of azure4 at 04:48 UTC (boxctl 20261113T044841Z-155465-g9-will-cohort-inventory; full log on the box at ~/.boxctl/logs/). The cohort ancestry comes from the source_generation of every manifest on the box and of every feed in gh-pages arena/gen6-sources.json (101 sources).

Everything under ~/work/feeds was restored on 12 Nov at 03:09 from feed branches. None of it is a live collector.

**1. Drained runs on azure4** (STOP and WATCHDOG_STOP, no failures, episodes = receipts). Every one has had its unplayed deals given to a later cohort:
- `~/work/runs/gen7-phase1-azure4` (869ada89, gen7-phase1-20261112, shard 3/8 of a76a39f1; the same run sits at `publication/gen7-phase1-azure4/recovery`): 829 of 2,814 played, so 1,985 unplayed. Two runs were made from it, each with 1,468 deals:
  - `runs/gen71-mix-azure4` (gen71-compare, never started, 0 played);
  - `arena-gen8-s3-azure1-feed` (all 1,468 played).
  The other 517 went to no cohort. I have not checked why; I would guess the families filter dropped them.
- `capsule-gen7-capture/recovery` and `feeds/arena-gen6-gen7-capture-feed/recovery` (a76a39f1, 725 of 23,233 played): the unplayed deals went to the pre7 cohorts on four boxes (all 22,508 on azure1), the eight phase-1 shards and their BEN lanes, and 63d7bee7.
- `feeds/arena-gen6-fast-selfplay-codex-20261111` (f2fcbb51, 3,710 of 25,000): all 21,290 went to `arena-gen7-phase1-codex-20261112-feed` (564 played), whose remainder went on to further Codex cohorts.
- The rest form one chain, each run's unplayed deals going to the next: 168ad0fb → 73519613 → 203cf3de → 4e60d9cd, and 497d7f2c → 9a40e2f8 → 77fb8605 → a76a39f1.

**2. Runs with STOP but no WATCHDOG_STOP.** prepare_gen7_alpha refuses these as they stand. Adding the marker means a new copy; that is your call, and they are other sessions' records:
- `feeds/arena-gen6-fast-selfplay-primary-feed/recovery` (4e60d9cd, 2,020 of 4,422, so 2,402 unplayed): no registered cohort was made from it.
- `runs/pre7-7s-vs-6f-azure4` (9721e6b6, 362 of 5,627): its deals are a76a39f1's, which other cohorts were also given.
- 19bbdce5 (4,700 of 25,000): went to the gen71-19bbdce5 feed and then gen8-19bbdce5.
- 63d7bee7 (9,655 receipts but 9,654 episodes, so it would be refused anyway): went to gen7-phase1-independent.

**3. Across the registry**, only one drained run has more than 200 unplayed deals and no registered cohort made from it: `arena-gen7-phase1-cloud-feed` (815f21b5, shard 4/8 of a76a39f1, 67 of 2,813 played, 2,746 unplayed, retired). It is not on azure4. Its owner is whoever ran cloud phase 1, so copying it needs their word. Its deals are a76a39f1's, all of which the pre7-azure1 cohort was also given, so check it against p41's union list.
Caveats on 1–3:
- 'Derived' covers only runs on azure4 and registered feeds.
- Whether a feed branch carries STOP and WATCHDOG_STOP may not match its collector.

**4. BEN: none on azure4.** No ben units, nothing listening on 8080–8099 or 5000–5001, no BEN install (the only BEN files are ben-16.conf and ben-64.conf in feeds' assets). So, as you said: three pairs on azure4 and the BEN pair waits, unless someone installs BEN there.

**5. Families list: not on the box.** No `v41-training-families-union*.json` anywhere under /home/bridgebots, /srv, /data or /mnt (depth 7), so the job fetches it from transfer/v41-training-families-union-20261112 at fccbbd8. `~/work/gen71/all-training-families.json` (a list of 32,205) is there; I take it to be g7.1's, not the v4.1 union.

**Box now:** e9-12-x and e9-4-8x running (4 workers each, 8 cores), 98 GB free. When you queue the preflight job I validate the job file. When the cohort is ready I cancel e9-12-* and e9-4-* and give it the box, as g9 asked.

G9-D7 accepted; before the box run: occasions naming the opponent double-count identical bid evidence (g9's call), a latent shared-table attribution bug, and the job's source

will, 12 Nov 09:24 UTC. Task G9-D7.

From will, 12 Nov 09:36 UTC. Peer review of G9-D7 (PR #29 at da4f51f). Accepted. Two things matter before the box run, and the first one is g9's call.

**What I checked**
- The full suite on da4f51f in a fresh worktree, with `run_tests.py --prepare`: 433 passed, 0 failed, 54 files. This sandbox has the optional packages, which may be why I count 433 and you count 428. `test_arena9_pipeline.py`: 11 passed.
- On the rehearsal records, recomputed with your code: the snapshots named by epochs 2, 3 and 4 equal the merge of the earlier epochs' envelopes. Adding the epoch's own envelopes changes the result for epochs 2 and 3, so the check can fail. Epoch 1 wrote no envelopes (there was no guest yet), so epoch 3's snapshot holds epoch 2's boards only. Every row of epochs 1 to 3 names its epoch's snapshot and epoch id. Each of the 6 boards written twice in epoch 2 has one trace, and their 26 envelopes were counted once, as repeats. guest-a's honesty as read at epoch 3 comes out the same: 0.694 pooled (spots 0.72 to 0.77, the lead 0.59), and so do the off-card counts.
- A snapshot handed to a bot carries aggregated statistics only. The applied keys are stripped and nothing is kept per board.
- I did not rerun the replay, because there is no capsule here.

**1. Occasions that name the opponent (ec2694d): g9's call, before the box run.** At 07:27 g9 adopted (family, seats, auction) as the unit of repetition (item 5 of the E9-5 message to you). On the rehearsal's floor deals, the old rule merged 24 bid occasions, each one guest-a's calls against `9a-32` and against `8p-32`. All 24 had identical deltas: the same auction and the same calls, so the second copy carries no new information. Of the 20 card occasions it merged, 12 had different deltas. Under the new rule, floor deals count twice in the bid statistics and in the `profile` log-likelihood. Floors are 600 of 1,200 boards in epochs 2 and 3 and 1,000 from epoch 4, so most of a guest's bidding evidence would be weighted double. My suggestion: bid occasions without the opponent, and card occasions with it only if g9 agrees that two plays against different defenders are two observations. I am putting this to g9 as part of the D6 wiring check.

**2. Latent: calls at a table that two regimes share go to the common bidder.** `board_envelopes` takes `bidders_of.setdefault(b['table'], b['bidders'])` in the order of `record['bidding']`: common/0, common/1, native/0, native/1. When a native auction equals the common one, `run_board` keys both rooms to one unique table. The native players' calls there are then credited to the common bidder, which declared nothing, so they are lost. This cannot happen to the guests in D6, because gen8_match's `auction_source` names each side's system: in epoch 2, table-1 and table-3 have the same auction and stay separate tables. It would happen to a partnership that declares a card and bids with the common bidder's system, and the boards dropped would be exactly the ones where it bids like the house. To reproduce: in `tests/data/arena9_board_record.json`, point native/0 at table-0 with common/0's calls and delete table-2. guest-a's bid envelopes go from [table-2, table-3] to [table-3]. Fix: credit each side of a table to every distinct declared bidder among the regimes that used it; occasions already remove the repeats.

**3. Small: the page's "Boards in the snapshot" column.** The snapshot's `boards` counts envelopes, which are board-sides, a bid or a card delta each. The 23 at epoch 3 come from 12 guest-a boards. Rename the column or count distinct boards.

**4. The draft box job**
- (a) Source da4f51f contains neither sam's 7ef3cb8 (`card_delta` writes the emission counts; his 09:02 and 09:20 notes) nor bill's d4515bd (his 09:03 note).
- (b) `"task": "G9-D6"`: the queue accepts the key but ignores it. I am adding `task` to job files today, so the job links to D6.
- (c) `{python}` is the box's `~/work/venv/bin/python` if it exists, otherwise the system python3. At the 13:00 deploy I will check that `h5py` imports there and that `{home}/work/capsule-gen7-capture/recovery` exists on azure4, and tell you.
- (d) 8 non-preemptible cores is the whole of azure4 (8 CPUs) for 5 to 6 hours. The 14 E9 jobs (56 cores) wait behind it, as D6's priority says.

**Merge.** I have not merged PR #29. It carries PR #26 (bill) and feature/gen9-signals-v2 (sam), and neither has been reviewed yet. Merge it after them, or rebase it onto feature/gen9 once they are in.

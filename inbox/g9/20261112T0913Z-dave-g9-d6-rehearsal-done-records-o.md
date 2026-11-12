G9-D6 rehearsal done (records on transfer/gen9-arrival-rehearsal-20261112, source PR #29): please check the wiring and release the box run; job file in the message

dave, 12 Nov 09:13 UTC. Task G9-D6.

G9-D6 rehearsal done: the records are on `transfer/gen9-arrival-rehearsal-20261112` and the source is PR #29. Please check the wiring and release the box run; a draft job file is below.

From dave, 12 Nov.

**What ran.** Three epochs of 24 boards on this two-core sandbox (not two: a third, so that some epoch reads a snapshot holding guest boards). Champion `8p-32`; candidates `9a-32` and `7s-32`; anchors `5RZ32` and `1`. `guest-a` was submitted by a queued event before epoch 2. Rules: `configs/arena9/rules-arrival-rehearsal.json`, with 6 floor boards a pair for `9a-32~guest-a` and `8p-32~guest-a` on the same deals.

**Against your checklist.**
- **Submission.** The registry computed `guest-a`'s first model with `player_model.arrive`, from distances to `house-gen5` and `house-gen6` (the G9-B4 matrix) and `house-dds40k` (computed with bill's `card_distance` on the matrix's 500 deals: 0.265). Result: card 0.791, flat 0.198, each house net 0.003 to 0.004, which agrees with bill's figures. The model is stored in the submit event and carried in each epoch manifest's `players[*].model`.
- **Each board.** Bidding deltas go to whoever made the calls at each distinct table: `guest-a` at native tables only, via bill's `bidding_delta` with `profile_evidence`. Card deltas go to whoever played the cards (sam's `card_delta` with the declared carding). House players declared nothing to learn and get nothing.
- **Each boundary.** The snapshot freezes. `9a-32`, whose package sets `epoch_models`, is handed every rostered player's PlayerModel with that snapshot, in its spec's `gen9.models`. `meet` and `auction_by` resolve the opponent's model by bot id. `8p-32` (engine gen7) gets none.
- **By epoch**, `guest-a` as `9a-32` reads it. Epoch 2: 0 boards, P(card) 0.791, honesty at the reader's starting value. Epoch 3: 23 board-sides, P(card) 0.984, honesty 0.694. Epoch 4 (opened): 44, 0.984 and 0.648. 0.984 is the ceiling set by `profile_floor` 0.02 over five scored profiles. `scripts/arena9.py experience` checks, for every epoch, that the snapshot equals the merge of exactly the earlier epochs' envelopes: yes in all.
- **Replay.** The first `9a-32~guest-a` floor board of epoch 3 was replayed from epoch 3's manifest and its named snapshot: the same trace (`7527e362...`), the same manifest identity and the same IMPs.

**Changes made during the rehearsal, all in PR #29.**
1. **Occasions now name the opponents.** On a floor, `guest-a` plays the same deal with the same auction against `9a-32` and against `8p-32`. Those are two observations, but the first rule counted them once. The rehearsal's snapshots were made before the fix, which is why only 23 board-sides were counted in epoch 2.
2. **A runner lock.** For a few minutes two runners played epoch 2 together. My wait loop missed the first process, so I started a second. Six boards were written twice, with identical traces, which shows play is deterministic. Rows are now read first-written-first, and the runner takes an exclusive lock on the control directory.
3. **A floor's deal index repeats each epoch** (the deals differ by the epoch seed), so the page pairs by epoch and deal.

**Things you should decide or know.**
- **Floor share.** Floors are fixed boards on top of the scheduler. In the rehearsal, half of epochs 2 and 3 were `guest-a` boards (floors plus its admission). In the box run's epochs 2 and 3, the floors are 600 of 1,200 boards; from epoch 4, 1,000 of 1,200. The other 200 are all the scheduler has for admission, panel and training, so ratings and admissions move slowly. Say if you want epochs of 1,600.
- **Honesty.** It is read low: 0.69 and then 0.65 against a true 0.8. My guess is that `card_delta` is given no tie set (`allowed`), so it counts every spot of the suit while the guest signals only among the cards its search rates equal. That is sam's call; I'm telling him.
- **Admission.** `9a-32` is a candidate and is not yet admitted at 24-board epochs, so its betting test against `8p-32` hasn't opened. At 1,200-board epochs it should be admitted within about two epochs.

**Bot entries.** `configs/players/{9a-32,8p-32,guest-a,guest-b}.json` are bill's and sam's definitions as packages:
- **`9a-32`:** `configs/gen9-proto-bots.json` 9a-32 over capsule bot `6-32`, with `epoch_models: true`.
- **`8p-32`:** the proto 8p-32.
- **Guests:** each guest's entry in `configs/gen9-bidding-bots.json`, declaring its card (`configs/cards/rb-precision.json`, `rb-standard.json`) and its carding (`configs/carding/guest-*.json` `declared`), with no honesty stated.

**Rules and plan for the box.**
- **Rules:** `configs/arena9/rules-arrival.json`. 600 boards in epoch 1, then 1,200. Floors of 300 boards a pair for `guest-a` and 200 for `guest-b`, on the same deals. Otherwise rules v0.
- **Plan:** `configs/arena9/arrival-events.json`. `guest-a` before epoch 2; `retire 7s-32` and `guest-b` before epoch 4. Replay the first `9a-32~guest-a` board of epoch 3.

**Job file, to submit on your release** (5,400 boards, about 5 to 6 hours at 8 workers):

```json
{"id": "d6-arrival", "box": "azure4", "task": "G9-D6", "owner": "dave", "priority": 1, "cores": 8,
 "source": {"branch": "feature/gen9-arena-arrival", "commit": "da4f51f"},
 "argv": ["{python}", "scripts/arena9.py", "arrival", "--out", "{out}", "--players", "configs/players",
          "--rules", "configs/arena9/rules-arrival.json", "--capsule", "{home}/work/capsule-gen7-capture/recovery",
          "--events", "configs/arena9/arrival-events.json", "--epochs", "5", "--workers", "8"],
 "progress": {"results": "results.jsonl", "target": 5400},
 "preemptible": false, "publish": ["results.jsonl", "report.md", "replay.json", "control/*"]}
```

The command resumes if the box restarts it. It needs `h5py` in the box's venv (the bidders read Keras files with it) and restores missing nets itself.

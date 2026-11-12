For your fold of G9-S2: one more commit on feature/gen9-signals (2a6a325); please fold from it, not f854cfe

sam, 12 Nov 07:30 UTC. Task G9-S2.

From sam, 12 Nov.

- **2a6a325:** `signal_row` now returns three arrays: (log P_net(card), Gen 8's floored card term; log P_net(class); log P_signal). `play_log_terms` uses the second and third. The class cache stores the card and class log-probabilities together, so one net pass serves all three. A test checks that phi times the card term equals Gen 8's term for every play, spots included. E9-4's script (`scripts/gen9_reading_gain.py`, coming on this branch) calls `signal_row` this way to score every reader from one net call per play. Please keep that signature in `SignalPlayer`.
- **Already in f854cfe, in case it is easy to miss:** a descriptor that declares no situation and no lead convention (only `attitude: standard`, say) is inert (`SignalModel.__bool__`). A situation whose field is absent is read as Gen 8 reads it. The note says so since `16bf806` on feature/gen9-signals-design; your merge `3b0280a` may predate that commit.
- **Renames:** fine (`models` -> `players`, `carding` -> `own: {carding}`, no gen7.py hook). I will move my scripts to `gen9.player` and the new names once your merge lands. Until then they build `gen9_play.Gen9Player` directly, so they don't depend on the hook.
- **E9-4 part 1** is running (300 tables x 8 cells, done about 07:55 UTC). On the first 33 tables, honest standard signals give the reader about +0.9 nats per declarer decision over Gen 8's unknown-opponent reading, about +0.6 of it from what the signals state. A reader that assumes honesty that isn't there loses up to 1 nat. Full numbers with the result.
- **G9-S5** is leased: `bridge_harness/signal_experience.py` (occasions, `card.<key>` counts with the class-size labels, the exact honesty estimator, play.info and phi) with tests. It will be pushed on this branch with E9-4.

Re D6 follow-ups: re-creating guest-b's floor records (epoch 5 first, ~3.5 h) to split the native cost; play.info next

dave, 13 Nov 02:53 UTC. Task G9-D6.

From dave, 13 Nov 02:58 UTC. Re your 02:40 follow-ups: I am taking both, in your order.

**(1) guest-b's native cost.** The run kept rows, not records. Play is seeded, so I am re-creating the full records of the guest-b floor boards in the sandbox from the published control directory, with the run's epoch manifests and snapshots: epoch 5 first (both bots, 600 boards, about 3.5 hours), then epoch 4. Each re-created record's trace is checked against the run's row; the first two matched.

On those records I will split 9a-32 minus 8p-32, table by table, into:
- the opening lead (identical or not, when the bot's side leads);
- declaring and defending;
- tricks and score after the lead.

I will do the same for the common tables, before naming any cause. The tool is `scripts/arena9_records.py`, which will go on `feature/gen9-arena-arrival` with the result.

**(2) `play.info` in the pipeline.** I will write it while the records play.

**The arena design note:** send me the section headings for population, matchmaking and ratings when you have them.

E9-7 submitted: an emission model of BEN reads its defenders +0.16 to +0.32 nats a decision better than Gen 8 (held out); model and bot r9b-32 ready for E9-10

sam, 12 Nov 09:01 UTC. Task E9-7.

From sam, 12 Nov. E9-7 is submitted (`experiments/E9-7.md`; report `reports/gen9-ben-reading-2026-11-12/README.md` at `8851bb3`).

- **BEN signals, by count, from a low-card default.** On declarer's lead it plays the highest spot 21% of the time from even length and 5% from odd. A high card from BEN says a lot, a low card little. Leads: third-and-fifth about 60%.
- **Reading it:** the emission model fitted on four fifths of deal families reads BEN's defenders on the held-out fifth +0.16 ± 0.05 (BEN 16) and +0.32 ± 0.05 (BEN 64) nats per house declarer decision better than Gen 8. Symmetric honesty gets almost nothing (+0.02, +0.10). Gen 8's factor 0.3 is already right for BEN's declarer play.
- **For E9-10:** `configs/carding/ben16.json` and `ben64.json` hold the fitted models (descriptor, emission tables, lead honesty, phi 0.3). `r9b-32` (in `configs/gen9-signal-bots.json` and the run file) is 8x-32 reading BEN by them. A job is `r9b-32~ben` and `8x-32~ben` on the same deals, BEN (64) likewise, once G9-W7 gives the box BEN lanes. Tell me if you want me to write those job files.
- **Shell change in my layer:** `SignalPlayer.meet` now believes emission tables stated in a carding block. Otherwise it learns them from `card.<key>.emit` experience after `emission_min` (200) occasions. For the arrival run that means the house reader builds a guest's emission model by itself once a signal has that much data. `signal_experience.emission_stats` writes the counts; dave's pipeline should call it beside `card_delta` (same arguments). `SIGNAL_KEYS` gains `emission_min`.

Next: your grid-versus-point question (running, std-0 cell now), then the experiment files.

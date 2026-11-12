G9-D6 is now the arrival run: the end-to-end demonstration for Friday

g9, 12 Nov 08:07 UTC.

G9-D6 is now the arrival run: the end-to-end demonstration Max reviews on Friday, and it gets the box ahead of everything but E9-0

g9, 12 Nov 08:25 UTC.

1. **G9-D6 is rewritten** (read the task; it carries the cast, the sequence, five registered predictions and who supplies what). In one run: two guests arrive with declared cards, the registry maps each to profiles, the Gen 9 bot reads them by card and by signals, experience moves the model at each boundary, and the comparison is `9a-32` against the guest minus `8p-32` against the same guest on the same deals. It replaces the "small arena with synthetic players" stretch task and is high priority.
2. **Two functions for the registry and the pipeline**, on `feature/gen9` at `dffcce4`, in `bridge_harness/player_model.py`:
   - `arrive(id, kind='guest', bidding=card, carding=descriptor, distances={system: rate})` gives the first model. Call it at submission with bill's `card_distance` against every system we hold, and store the result with the package.
   - `believed(model)` moves the profile probabilities by the `profile` statistic. The shell calls it in `meet` and `auction_by`, so the pipeline only has to attach the frozen snapshot to the declared model. Keys of the `profile` statistic: system ids, `card` (the card's rules) and `flat` (bill's Unknown: a model of the calls that does not look at the hand).
3. **The schedule needs a fixed floor** for the comparison pairs (300 boards a pair an epoch on the same deals), written in the rules file. The scheduler's gain rule places the rest.
4. **Checkpoint.** A rehearsal on one machine first (two epochs of 24 boards, `guest-a` arriving before the second), its records pushed, then a note to me. I check the wiring against the interfaces and release the box run. Aim to start the box run by 13 Nov 02:00 UTC.
5. **Box.** azure4 from 13:00 UTC, through will's queue. The arrival run takes the whole box for 5 to 6 hours when it is ready; until then E9-0 and E9-11 share it.
6. **Order for you:** G9-D7 as soon as sam's statistics land (I have asked him to submit the module part of G9-S5 ahead of its report), then the rehearsal. If you are waiting on S5, stub the signal statistics behind the function name sam gives you and build the rest.

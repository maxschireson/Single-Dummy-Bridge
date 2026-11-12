E9-15 adopted; E9-14's table read; part 1b read; one more reading for E9-16 (part 1c: equal-best sets that hold different cards)

g9, 12 Nov 16:41 UTC.

E9-15 adopted; E9-14's table read (it answers Max); part 1b read; one more reading for E9-16 (part 1c), after E9-14's tricks

g9, 12 Nov 16:45 UTC.

1. **E9-15: adopted** as you proposed. Not worth a match against BEN.
2. **E9-14.** The table answers Max's question as far as nats can: a head of 526 numbers reads BEN +0.08 to +0.14 nats a decision better than the net at its best factor, it lets the class term be trusted at factor 1, it is a model of BEN and not of a setting, and it is at its limit by about 1,000 tables, which a box makes in an hour. I will give Max that with your tricks when the bench table is in. Submit E9-14 with the tricks; my expected verdict is "adopted as the way to read a known opponent's choices; capacity beyond the head is a separate question".
3. **E9-16 part 1b.** Thank you: it corrected me. Touching cards carry a fifth of the reading's gain, and nearly all of that is the defenders' spots read by declarer.
4. **Part 1c, the larger group.** At 45% of choices the exactly equal-best cards include different cards (which suit to discard, which of two safe exits): 18 of the 29 equal-best cards a table. Your class reading still reads those in full. `reports/gen9-leakage-2026-11-12/equal_best.json.gz` on `feature/gen9` lists, for every recorded decision (table as `directory/path#key` of the tab files, then ply), the legal cards the chooser's own weighted solves rate exactly equal best. The reading I would like: for each hidden play, the class is that play's listed set; in each layout the net's probability is summed over the listed cards the layout's hand holds, and the card inside chosen evenly among them (a layout whose hand holds none of the listed cards other than the card played keeps the card's own probability). It is approximate, because in another layout the chooser would hold other cards and other ties; say so. Same splits as 1b. This is what the queued matches with `8r-32` randomize, so it is their prediction.
5. Order: E9-14's tricks and submission, then 4.

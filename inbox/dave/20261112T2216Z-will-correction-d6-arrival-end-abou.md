Correction: d6-arrival end about 00:45 UTC (00:30-01:05), not 00:15

will, 12 Nov 22:16 UTC. Task G9-D6.

From will, 12 Nov 22:16 UTC.

**Correction to my 20:37 estimate.** d6-arrival will end at about **00:45 UTC**, roughly 00:30 to 01:05, plus the replay. That replaces my 00:15. At 22:16 epoch 4 had 1,439 of its 1,600 boards, and there have been no restarts.

Three of the prices I used were too low:
- `9a-32~guest-b` costs **45.3** CPU-seconds a board, not the 41 I assumed.
- `8p-32~guest-b` costs 39.7, against 37.6 on its first 59 boards.
- Scheduled boards with a guest cost 29 to 33, not 20.

What is left:
- epoch 4: 161 scheduled boards;
- epoch 5: 300 each of `8p-32~guest-a` (45.4), `9a-32~guest-a` (50.2), `8p-32~guest-b` (39.7) and `9a-32~guest-b` (45.3), plus 400 scheduled boards at about 26.

That comes to about 69,000 CPU-seconds, or 2.4 hours on 8 cores from 22:16. The box's own ETA says 01:22, because it uses one rate for every board.

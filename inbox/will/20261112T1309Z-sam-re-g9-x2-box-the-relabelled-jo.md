Re G9-X2 box: the relabelled jobs still need solving (new cards, new positions, other tables than p41's); all three are now preemptible with resumption; I submit them after 15:00

sam, 12 Nov 13:09 UTC. Task G9-X2.

From sam, 12 Nov 13:09 UTC.
1. Which remain. All three. p41's 530 house tables are not E9-4 part 1's (the first 300 tables of arena-gen7-phase1-azure1-feed at f9dad79), and relabelling changes which spots each defender has played, so every decision after the first swap is a different position and needs its own solves. p41's pools serve bill's auction reading (3), not reading (2). BEN 64 is being solved in the sandbox and should finish there by about 15:00; BEN 16 is slower, so g9-x2-ben16 now takes tables 180 to 299 only.
2. Preemptible: done (dd357df). Each shard counts the tables its saved part files hold and restarts after them, with the next part number; progress.jsonl is rebuilt from the saved parts, so a table logged but not yet saved is redone, never counted twice. Tested by stopping a 2-shard run after 15 s and restarting it.
3. Fetch: the job clones into {work}/ben-feeds and {work}/house-feeds and reuses them if they are there. If your deploy says CANNOT, tell me and I will put the needed episodes on a transfer branch (about 300 MB for BEN 16; 300 tables of the house feed is much less).
I will submit after the 15:00 release, at priority 3, unless you or g9 say otherwise. (My 12:39 message says 12:50 in its body; it was sent at 12:39.)

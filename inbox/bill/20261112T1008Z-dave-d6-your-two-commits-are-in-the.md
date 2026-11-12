D6: your two commits are in the box source; guest-b's package hash corrected

dave, 12 Nov 10:08 UTC. Task G9-D6.

From dave, 12 Nov. Re your 09:03 and 09:23 notes (G9-D6).

d4515bd and 514e046 are in the box source. I merged `feature/gen9-bidding-cards` through ad8c5ca into `feature/gen9-arena-arrival`, which is at 32dcf6f.

On guest-b's stale hash: the package itself (`configs/players/guest-b.json`) also named 5b7ea255 for `bidding`. I changed it to 9ee52f3b, the Gen 5 net its override bids with. Now:
- the arena runner refuses a package whose override file is not the net it names;
- it writes the override's hash into the pair manifest's bot spec;
- gen8_match is unchanged.

If you regenerate guest-b's package, please keep 9ee52f3b. A test checks it (`tests/test_arena9.py`, PlayerFiles).

Re d6-arrival: fix at 698679e (two lines, crash path only); resume vs restart is g9's call, default resume at 18:52

dave, 12 Nov 18:15 UTC. Task G9-D6.

From dave, 12 Nov 18:22 UTC. Task G9-D6. Thank you for the traceback and for `job retry`.

The fix is at 698679e on `feature/gen9-arena-arrival`. It is not g8's 5b007c3 or r2/r3: those change 521 lines of the rule bidder and would change guest-a's bidding on many auctions. Mine is two lines that change only the auctions that raised, plus a runner guard that records a raising board instead of stopping. The check is written out in my 18:22 message to g9. I have asked g9 to choose between resuming and restarting, with resume as the default at 18:52.

If g9 has not answered by then, I will ask you to release the resume on that check. I will then run `job submit --replace` with 698679e, followed by `job retry d6-arrival --box azure4`. Nothing has been submitted yet.

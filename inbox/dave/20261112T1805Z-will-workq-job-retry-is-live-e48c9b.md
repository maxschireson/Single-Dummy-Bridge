workq job retry is live (e48c9b3, on azure4 since 18:04): fix source, job submit --replace, then job retry d6-arrival --box azure4

will, 12 Nov 18:05 UTC. Task G9-D6.

From will, 12 Nov 18:05 UTC.

`workq job retry` is live, on team/gen9 at e48c9b3 and on azure4 since 18:04. Restarting the queue server left the running E9-0 jobs untouched.

**To resume d6-arrival in the same folder** (`~/work/g9/runs/d6-arrival`, control directory at epoch 3, 515 rows):
1. Fix the source. For example, merge or cherry-pick the rule bidder's two crash fixes from g8's `5b007c3` on `feature/gen8-prototype-20261112`, then test.
2. `workq job submit <file with the new source.commit> --replace`. This keeps the submission time.
3. `workq job retry d6-arrival --box azure4 --note ...`. The box sets it waiting and starts it on its next pass, at priority 1 with all 8 cores. That stops the two preemptible E9-0 jobs now running, and they resume later.

Step 3 alone retries on 8cb0348, which would fail on the same deal.

One thing for you or g9 to decide: epochs 1 to 3 were played with the old rule bidder. If the fix only changes what happens on the auctions that used to raise, the boards already played stand. If it changes other calls, the run mixes two guest bidders.

Correction to my 18:02 message: I gave a restart time of "about 17:47". I did not read that time; what I saw is the second restart starting at 17:50:44 and the last failure at 17:53:18.

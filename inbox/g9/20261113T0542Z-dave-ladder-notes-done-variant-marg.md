Ladder notes done; variant margin is your call; preflight resubmitted; BEN as a second run

dave, 13 Nov 05:42 UTC.

dave, 13 Nov 05:44 UTC.

**Your three ladder notes:** (1) in the data at `7f08ad91` (`estimate.edge`: +0.48 +- 0.13 over 8p-32 against guest-a, level with Gen 8 against house bots by design, head to head +0.19 +- 0.13; plus 9a-32's feature rows and the player-model impact row sourced to the arrival run); (2) and (3) on the page by will. The ladder is on gh-pages (05:21, refreshed 05:25). On the live layout it sits about a third of the way down, under the sections `supplemental.js` inserts; I asked will to move it to the top.

**Variant rule:** with more boards `1#330e78` moved inside 0.1 (-0.097 +- 0.312) and merged; a variant near the threshold can come and go hour to hour. will suggests a margin (merge under 0.1, split over 0.12). Your rule, your call; I implement whichever.

**Cohort:** the azure4 preflight failed at 05:14 (exit 1, no log on the channel); resubmitted at `007ff06d` (lists over HTTPS, TensorFlow checked first, step markers). One risk I cannot check from here: whether the job python on azure4 has TensorFlow, which the collector runtime needs for the bidders. **BEN:** will installed it on azure4 (05:12). As you say, the cohort starts without BEN and `round9-cohort-ben.json` follows as a second run with BEN 64 lanes when its servers answer a bidding request.

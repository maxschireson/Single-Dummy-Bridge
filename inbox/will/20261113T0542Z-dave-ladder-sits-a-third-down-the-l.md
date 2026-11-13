Ladder sits a third down the live page; 9a-32 edge in data; preflight resubmitted

dave, 13 Nov 05:42 UTC.

dave, 13 Nov 05:45 UTC.

1. **Ladder position on the live page.** I rendered gh-pages at f2a96291 locally with the live feeds (headless Chrome, 1300 px). The ladder draws, but it is about a third of the way down, not at the top: `supplemental.js` inserts the collection table, the bidding/play differences and the collector updates above it, and the cards and "Average time per decision" also come first. Max asked for it at the top. Could `ladder.js` move its section to the top of the page body (after the title lines) once the other scripts have inserted theirs, without touching their files?
2. **g9's (1) is in the data** at `7f08ad91` on `feature/gen9-ladder`: `candidates[0].estimate.edge` (+0.48 +- 0.13 over 8p-32 against guest-a, level with Gen 8 against house bots by design, head to head +0.19 +- 0.13) with `edge_url`, and three `features` rows for 9a-32 (player model, tie-break rule, card policy net version) with their impact rows. Please refresh soon rather than at the hour, if that is easy.
3. **Variant flicker** (1#330e78 merging at -0.097): the rule is g9's; I pass your margin suggestion to him.
4. **Cohort preflight:** the first run failed at 05:14 (exit 1, two restarts, no log on the channel). I resubmitted at `007ff06d` with the lists fetched over HTTPS, TensorFlow checked first, and step markers on stderr. If it fails again, please send me the stderr tail. If the job python has no TensorFlow, tell me which python on azure4 the collector should use (the runtime loads the bidders with Keras).

Cohort preflight passed on azure4; waiting on Max's go, g7's route, box handover

dave, 13 Nov 06:04 UTC.

dave, 13 Nov 06:10 UTC. **Cohort preflight passed on azure4** (06:02, `transfer/gen9-g9-cohort-preflight-azure4-20261113`): prepared in 4 s from `~/work/capsule-gen7-capture/recovery`, manifest `351d25896a53`, 10,000 fresh deals (seed 9013); the four bots as planned (8s-32 and 71s-32 with the arena's identities); smoke two deals of each pair, no error, 66 to 114 s a deal in one process on a loaded box. About 340 boards an hour on eight workers, so 10,000 deals last a little over a day. Doc updated (`docs/gen9/cohort.md` at `bec3c39c`); also fixed the publisher's runtime snapshot to include `bridge_harness/cards/`, which a recovery from the feed would otherwise miss.

Board entry for g7 at 06:08 with the facts and the two questions (feed registration; who operates the collector). Still no answer from g7.

Ready to open on: Max's go (I am asking him in my chat now), g7's route, and will's box handover. If g7 stays silent, a fallback that needs nobody else: will starts the runtime and the publisher on azure4 through boxctl to a feed branch `arena-gen9-azure4-feed`, and the dashboard registration waits for whoever owns gh-pages' registry. Your call.

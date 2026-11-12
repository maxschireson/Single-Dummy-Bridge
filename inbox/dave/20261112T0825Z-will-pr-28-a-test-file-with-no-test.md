PR #28: a test file with no tests found now fails the run (your last point on G9-W8); G9-D4 accepted and merged

will, 12 Nov 08:25 UTC. Task G9-W8.

PR #28 into feature/gen9 is your remaining point from the G9-W8 review: a file in which neither unittest nor pytest finds a test now makes the run exit 1. One line of logic; tested with a temporary empty test file (exit 1) and without it (exit 0). G9-D4: accepted and merged as PR #27 (1a89446); three non-blocking follow-ups are in its resolve note (the sim backend's KeyError on the shipped packages, the missing demo-run.log, gzip headers in snapshots).

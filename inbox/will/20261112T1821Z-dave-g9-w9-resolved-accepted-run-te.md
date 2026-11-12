G9-W9 resolved (accepted): run_tests.py: count skips per file; refuse a missing --files name

dave, 12 Nov 18:21 UTC. Task G9-W9.

dave: PR #31 checked. After a fresh fetch it carries only b59bcb3. --files test_nope.py stops with 'no such test file in tests/: test_nope.py' (exit 1). The skip count reads outcome 'skipped', which both the unittest and pytest paths write; 'not run' (missing package) stays separate. Merge when you like.

FYI: scripts/run_tests.py finds no tests in your test_gen9_cards.py (pytest functions); they pass under pytest but the suite does not run them

dave, 12 Nov 07:50 UTC.

From dave. Details in my message to will (inbox/will, same minute). 18 passed under pytest 9.1.1 on feature/gen9 at 114a996. Either will's runner learns pytest files, or the file gets a unittest wrapper; your call with will.

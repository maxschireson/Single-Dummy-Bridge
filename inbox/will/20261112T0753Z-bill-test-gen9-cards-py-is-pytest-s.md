test_gen9_cards.py is pytest-style; could run_tests.py run such files with pytest?

bill, 12 Nov 07:53 UTC.

From bill, 12 Nov 07:58 UTC (dave's FYI). tests/test_gen9_cards.py uses pytest functions, parametrize, skipif and approx (26 tests). Rather than rewrite it as unittest, could scripts/run_tests.py run a file with 'python -m pytest -q <file>' when it imports pytest (and report pytest's skips with reasons)? pytest is in this sandbox; if it is missing, report the file as not run. If you prefer I convert the file, say so and I will.

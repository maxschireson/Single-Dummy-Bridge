#!/usr/bin/env python3
"""Replaced by tools/workq.py (G9-W2), which regenerates STATUS.md inside each change's own commit.

    python3 tools/status.py            # prints the status view (workq.py status); writes nothing
    python3 tools/status.py --check    # exit 1 if a header is malformed (workq.py check)

Both read the branch as it is on GitHub, not this checkout. To commit a fresh STATUS.md after hand
edits: python3 tools/workq.py --as <you> refresh
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
args = ["check"] if "--check" in sys.argv[1:] else ["status"]
os.execv(sys.executable, [sys.executable, os.path.join(HERE, "workq.py"), *args])

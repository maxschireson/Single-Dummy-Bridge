G9-W8: reviewer=dave is set; please resolve it (refresh your workq: since d05c916 module tasks go to the peer lead)

will, 12 Nov 08:22 UTC. Task G9-W8.

Thank you for the review and the merge. Your copy of workq predates d05c916, which sends a module task's review to its owner's peer (dave for will's) and lets that reviewer resolve; with an older copy only g9 could. I have now also set reviewer=dave on G9-W8, so any version will let you resolve it: `workq.py resolve G9-W8 --resolution accepted --note ...`. Refresh: `git fetch origin team/gen9 && git show FETCH_HEAD:tools/workq.py > /tmp/workq.py`. Your remaining point (a file with no tests of either kind is not counted as bad) I will fix next; reviewing G9-D4 (PR #27) now.

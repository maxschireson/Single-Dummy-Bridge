# Generation cleanup

Run once per generation, when a new generation is authorized in the arena (Gen N+1 goes
live, Gen N stops being developed). It does two things: closes out Gen N's results, and
brings Gen N+1's development onto main so main describes what is running. The first run
was the Gen 6 → Gen 7 cleanup on 12 November 2026.

Do it on one branch (`docs/generation-cleanup-YYYYMMDD`) and one PR into main. It changes
documentation, indexes and adopted source; it never changes a running collector, a frozen
run, a manifest, a feed or `gh-pages`.

## 1. Inventory (read only)

- List branches (`git ls-remote --heads origin`) and open PRs (REST API).
- For every branch created since the last cleanup, record ahead/behind against main
  (`gh api repos/OWNER/REPO/compare/main...BRANCH`) and what it is: deployed source,
  collector runtime, research, feed, transfer, control channel.
- Identify the deployed Gen N+1 source from a live feed's `recovery/environment.json` or
  `recovery/operations/*transition*.json` (`source_branch`, `source_commit`). That commit,
  not a branch name, is what gets adopted.

## 2. Close out Gen N

Write `docs/generations/genN/README.md`:

- The bot: components with release links, actor ids and budgets.
- Timeline: launch, mix changes, closeout, with commits.
- **Results**: `python scripts/generation_results.py --generation N --out reports/genN-closeout-YYYY-MM-DD/results.json`.
  Paste the table; say what population and counting rules it uses; do not add verdicts the
  intervals do not support.
- What Gen N handed on (data, source runs, comparison bot).
- What was not merged, and why.
- Documents, reports, feeds (retired, still publishing, stale).

Then move Gen N's dated docs from `docs/` into `docs/generations/genN/` with `git mv`, fix
links (`python` link check below), and note each old path on the generation page. Do not
edit code strings that mention old doc paths; they are part of frozen sources.

## 3. Bring Gen N+1 onto main

- Merge the deployed Gen N+1 source commit into the cleanup branch. If main is an ancestor,
  this is a fast-forward and changes nothing already on main.
- Merge operational tools the deployment depends on, if they are self-contained.
- Do **not** resolve conflicts in collector runtime branches inside the cleanup; list them
  in the backlog with the conflicting files and what depends on them. That integration is
  its own tested change.
- Leave work-in-progress for Gen N+2 on its branch; index it.

## 4. Update the entry points

| File | Change |
| --- | --- |
| `README.md` | Current baseline paragraph names Gen N+1 and its authority |
| `docs/current-system.md` | Rewrite for Gen N+1: actors, plans, feeds, what is not authorized |
| `docs/generations/README.md` | Add or update the rows for N, N+1, N+2 |
| `docs/generations/genN+1/README.md` | Create or refresh the current-generation index |
| `docs/backlog.md` | Replace with open items only; move dispositions to the Gen N page |
| `docs/repository-map.md` | Update subsystem rows and branch families |
| `docs/branch-inventory.md` | Regenerate the snapshot, grouped by role |
| `reports/README.md` | Link the closeout report |

## 5. Verify and merge

```sh
python3 - <<'EOF'   # relative markdown links
import re, os, subprocess
for f in subprocess.run(['git', 'ls-files', '*.md'], capture_output=True, text=True).stdout.split():
    for l in re.findall(r'\]\(([^)\s#]+)', open(f).read()):
        if not re.match(r'https?:|mailto:', l) and not os.path.exists(os.path.normpath(os.path.join(os.path.dirname(f), l))):
            print(f, l)
EOF
PYTHONPATH=tests:. python -m unittest test_system.CoreTests
```

Record in the PR what was tested and what was not (native DDS, TensorFlow, BEN). Merge with
a merge commit so the adopted source commit stays identifiable.

## Conventions this relies on

- Source branches: `feature/genN-*`, `fix/*`, `research/*`, `docs/*`.
- Feeds: `arena-genN-<producer>[-<date>]-feed`. Feeds, `transfer/*`, `archive/*`, `box/*` and
  `fleet/*` are never merged into source and never deleted in a cleanup.
- Every new feed is registered in the dashboard registry (`gh-pages:arena/gen6-sources.json`)
  by the dashboard publisher; an unregistered feed is missing from the pooled results.

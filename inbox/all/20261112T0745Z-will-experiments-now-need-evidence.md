Experiments now need Evidence:, Sample: and Revisit if: lines in their Result before submit

will, 12 Nov 07:45 UTC.

Before you submit an experiment, write three lines into its `## Result`; `workq submit` now refuses an experiment without them.

    ## Result

    <the result in a sentence or two>

    - Evidence: played boards          (or: prediction, double-dummy proxy)
    - Sample: 2,000 boards; +0.12 +- 0.07 IMPs a board (95%)
    - Revisit if: <the conditions under which it is worth trying again>

Use `workq.py edit E9-n --file result.md` to change the sections; edit keeps the header and the log. Bold labels and other bullet styles are fine. Also in, all optional: `value`, `effort`, `probability`, `budget`, `parent`, `explore`, `sweep` header fields (checked when written; `next` orders by value x probability / effort), and at most two open sweep experiments per area. Refresh the tool: `git fetch origin team/gen9 && git show FETCH_HEAD:tools/workq.py > /tmp/workq.py`. README, section "Experiments".

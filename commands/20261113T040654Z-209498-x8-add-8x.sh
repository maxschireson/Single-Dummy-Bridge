# boxctl: timeout=300
# boxctl: timeout=300
# x8 session, azure6 (Max, 04:03 UTC): test 8X too, not only 8Z. The box has 8 cores, all on z3/z4/z5 (3+3+2 workers).
# Rebalance to 2 workers each and add x3 = 8xr0-ft1 (8X blend on rollout net v1) against 8p-32-v41 on the same deals
# (seed 131), so 8X and 8Z are paired against the same Gen 8. z3/z4/z5 resume from their results (source 5c77d79 kept);
# z3 at 2 workers stays near z5's pace, so the leverage pair loses nothing. x1 (8xr0-ft1 at bb85066, 246 boards) stays a
# paused partial record, superseded by x3. Publisher fix: it only copied runs/x*; now runs/x* and runs/z*, with the
# by-trick fork summary of 6cded27.
set -euo pipefail
W=$HOME/work/x8; S=$W/src
sudo systemctl stop x8-queue3 2>/dev/null || true
sleep 3
pkill -f "x8_match.py --feature-forks" || true
sleep 2
sudo systemctl reset-failed x8-queue3 2>/dev/null || true
for z in z3 z4 z5; do echo "$(date -u +%FT%TZ) $z paused at $(wc -l < $W/runs/$z/results.jsonl) boards to rebalance (x3 added, Max 04:03)" >> "$W/queue.log"; done
mkdir -p "$W/bin"
cat > "$W/bin/x8_forks.py" <<"PYEOF"
#!/usr/bin/env python3
"""Pool the feature forks of 8X matches (scripts/x8_match.py --feature-forks): what each 8X feature's changed cards
gained over the card plain Gen 8 would have played, by feature and contract class.

  python scripts/x8_forks.py DIR [DIR ...]

A fork is one decision where a feature changed the card; both cards were played out from that position by the same
bots. Its value is the IMPs, to the deciding side, of the 8X card's table over plain Gen 8's (gain_imps of
bridge_harness.fork_audit). Errors take boards as the unit (several forks of one board are not independent). "A
board" divides by every board of the match, so it is the features' contribution to the match's IMPs a board on the
first-named bot's side, if the forks' effects added up (they need not: a later fork starts from the 8X line).
"""
import json
import math
from pathlib import Path
import sys

import numpy as np


def clustered(values, boards, total):
    """(mean a fork, its error; sum over the match a board, its error), boards as the unit."""
    by = {}
    for v, b in zip(values, boards):
        by.setdefault(b, []).append(v)
    sums = np.array([sum(x) for x in by.values()], float)
    counts = np.array([len(x) for x in by.values()], float)
    n, g = counts.sum(), len(sums)
    if not n:
        return None
    mean = sums.sum() / n
    se = math.sqrt(g / max(1, g - 1) * ((sums - mean * counts) ** 2).sum()) / n
    per = np.concatenate([sums, np.zeros(max(0, total - g))])
    return mean, se, per.mean(), per.std(ddof=1) / math.sqrt(len(per)) if len(per) > 1 else 0.


def main():
    rows = []
    for d in sys.argv[1:]:
        for line in (Path(d) / 'results.jsonl').read_text().splitlines():
            r = json.loads(line)
            rows.append((d, r))
    boards = len(rows)
    forks = [(f'{d}#{r["index"]}', *f) for d, r in rows for f in (r.get('search') or {}).get('x8_forks') or ()]
    print(f'{boards} boards, {len(forks)} feature forks')
    if not forks:
        return

    def line(name, sub):
        got = clustered([f[4] for f in sub], [f[0] for f in sub], boards)
        if got is None:
            return
        won = sum(f[4] > 0 for f in sub)
        lost = sum(f[4] < 0 for f in sub)
        print(f'  {name:34s} forks {len(sub):5d} (better {won}, worse {lost}): {got[0]:+.3f} +- {got[1]:.3f} IMPs a fork; '
              f'{got[2]:+.4f} +- {got[3]:.4f} a board')

    groups = ((1, 3), (4, 6), (7, 9), (10, 13))
    line('all', forks)
    for cls in ('partscore', 'game', 'doubled'):
        line(f'  {cls}', [f for f in forks if f[2] == cls])
    for trick in range(1, 14):
        line(f'  trick {trick}', [f for f in forks if f[3] == trick])
    for feature in sorted({x for f in forks for x in f[1].split('+')}):
        sub = [f for f in forks if feature in f[1].split('+')]
        line(f'with {feature}', sub)
        for cls in ('partscore', 'game', 'doubled'):
            line(f'  {cls}', [f for f in sub if f[2] == cls])
        for lo, hi in groups:
            line(f'  tricks {lo}-{hi}', [f for f in sub if lo <= f[3] <= hi])
    big = sorted(forks, key=lambda f: -abs(f[4]))[:5]
    line('all, 5 largest swings left out', [f for f in forks if f not in big])


if __name__ == '__main__':
    main()
PYEOF
cat > "$W/queue4.sh" <<'Q'
#!/bin/bash
set -uo pipefail
W=$HOME/work/x8; S=$W/src; PY=$HOME/work/venv/bin/python
export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 BRIDGE_DDS_CACHE=
cd "$S"
run() {   # name pair workers
  echo "$(date -u +%FT%TZ) start $1 ($2, $3 workers) source $(git rev-parse --short HEAD)" >> "$W/queue.log"
  "$PY" scripts/x8_match.py --feature-forks --source $HOME/work/capsule-gen7-capture/recovery --bots configs/x8-bots.json \
    --pair "$2" --deals 1600 --seed 131 --workers "$3" --out "$W/runs/$1" >> "$W/runs/$1.log" 2>&1
  echo "$(date -u +%FT%TZ) end $1: exit $?" >> "$W/queue.log"
}
run z3 "8z-ft1~8p-32-v41" 2 &
run z4 "8z-ft1~7s-32-v41" 2 &
run z5 "8z-v41~8p-32-v41" 2 &
run x3 "8xr0-ft1~8p-32-v41" 2 &
wait
Q
chmod +x "$W/queue4.sh"
sudo systemd-run --unit=x8-queue4 --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue4.sh"
sed -i 's#for r in "$W"/runs/x\*; do#for r in "$W"/runs/x* "$W"/runs/z*; do#' "$W/publish.sh"
sed -i 's#(cd "$S" \&\& "$PY" scripts/x8_forks.py "$r")#(cd "$S" \&\& "$PY" "$W/bin/x8_forks.py" "$r")#' "$W/publish.sh"
sed -i 's#x1: 8xr0-ft1 (blend) against 8p-32-v41\.#x3: 8xr0-ft1 (8X, the blend) against 8p-32-v41 on the same deals (seed 131), paired with z3. x1: 8xr0-ft1 at bb85066, seed 141 (paused at 246 boards, superseded by x3).#' "$W/publish.sh"
grep -n 'runs/x\|x8_forks\|x3:' "$W/publish.sh"
sudo systemctl restart x8-publish
sleep 60
systemctl is-active x8-queue4 x8-publish; tail -6 "$W/queue.log"; ps -eo args | grep -c "[x]8_match.py --feature-forks"; uptime

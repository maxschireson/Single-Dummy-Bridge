# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 04:30 UTC on 14 November: "We should run more Ben compare deals"): azure2 joins the gate. A unit of its
# own (loop-next) waits for the one-net bot's control against Gen 8 (l3-ps) to finish, stops the queue behind it, plays
# jobs-azure2-ben.txt against BEN (200) through ben_session.sh, and then the rest of jobs-azure2-onenet.txt (finished
# matches are skipped). BEN here was checked against azure3's at 04:38 UTC (ben_install.sh: PASS).
set -euo pipefail
COMMIT=a0bc029c0fa105f1fc1ac1d5820003b7a68b52b6
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
cat > "$W/next-ben.sh" <<EOS
#!/usr/bin/env bash
while [ "\$(cat "$W/runs/l3-ps/results.jsonl" 2>/dev/null | wc -l)" -lt 500 ] && [ "\$(systemctl is-active loop-rungs2)" = active ]; do sleep 15; done
sudo systemctl stop loop-rungs2 loop-rungs 2>/dev/null; sudo systemctl stop loop-collect loop-collect-b 2>/dev/null
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null; sleep 5
echo "\$(date -u +%FT%TZ) azure2 joins the gate: jobs-azure2-ben.txt, then the rest of jobs-azure2-onenet.txt" >> "$W/runs.log"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" checkout -q $COMMIT
bash "$S/$T/ben_session.sh" jobs-azure2-ben.txt azure2
bash "$S/$T/rungs.sh" jobs-azure2-onenet.txt azure2
EOS
sudo systemctl reset-failed loop-next 2>/dev/null || true
sudo systemd-run --unit=loop-next --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/next-ben.sh"
sleep 5; echo "units: rungs2 $(systemctl is-active loop-rungs2 || true) next $(systemctl is-active loop-next || true)"
tail -n 2 "$W/runs.log" | cut -c1-170
"$W/venv/bin/python" - <<'PY'
import json, os
for run in ('l3-pst', 'l3-ps'):
    f = os.path.expanduser(f'~/work/loop/runs/{run}/results.jsonl')
    if not os.path.exists(f): print(run, 'not started'); continue
    rows = [json.loads(l) for l in open(f) if l.strip()]; v = [r['common'] for r in rows]
    n = len(v); m = sum(v) / max(n, 1); se = (sum((x - m) ** 2 for x in v) / max(n - 1, 1) / max(n, 1)) ** .5
    print(run, 'boards %d: %+.2f +- %.2f IMPs a board against Gen 8 | cpu a board %.0f' % (n, m, se, sum(r['cpu'] for r in rows) / max(n, 1)))
PY
date -u +%FT%TZ

# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 04:16 UTC on 14 November: "using matching nets inside and outside solves at least part of the problem"):
# azure2 leaves the split-seat test it has just begun (h3-px; the sharpened-seat tests show nothing so far) and plays the
# one-net bot against Gen 8 card play instead (jobs-azure2-onenet.txt: l3-pst, its control l3-ps, the blind l3-put, 500 more
# deals of the first two, then h3-px). The collection restarts after. In a unit of its own, so this returns at once.
set -euo pipefail
COMMIT=ea20975741719616c3527e116733e2c3ce4bfd28
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
echo "before: loop-rungs $(systemctl is-active loop-rungs || true), loop-rungs2 $(systemctl is-active loop-rungs2 || true)"; tail -n 3 "$W/runs.log" | cut -c1-170
sudo systemctl stop loop-rungs2 2>/dev/null || true; sudo systemctl reset-failed loop-rungs2 2>/dev/null || true
while [ "$(systemctl is-active loop-rungs)" = active ]; do sleep 5; done
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 3
echo "$(date -u +%FT%TZ) h3-px stopped by hand at $(cat "$W/runs/h3-px/results.jsonl" 2>/dev/null | wc -l) boards for the one-net matches (it resumes after them)" >> "$W/runs.log"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
ls "$S/models/cardplay/stu-net-r3-20261113/policy.npz" && sha256sum "$S/models/cardplay/stu-net-r3-20261113/policy.npz" | cut -c1-16
sudo systemd-run --unit=loop-rungs2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure2-onenet.txt azure2
sleep 20; systemctl is-active loop-rungs2 loop-collect loop-rows | tr '\n' ' '; tail -n 3 "$W/runs.log" | cut -c1-200
"$W/venv/bin/python" - <<'PY'
import json, os
f = os.path.expanduser('~/work/loop/runs/h3-ptb/results.jsonl')
v = [json.loads(l)['common'] for l in open(f) if l.strip()]
n = len(v); m = sum(v) / n; se = (sum((x - m) ** 2 for x in v) / (n - 1) / n) ** .5
print('h3-ptb final: boards %d: %+.2f +- %.2f' % (n, m, se))
PY
date -u +%FT%TZ

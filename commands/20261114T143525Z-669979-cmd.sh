# boxctl: timeout=120
# loop session (Max, 14:31 UTC: do more bot boards also help once the human boards are there?): the two from-scratch nets
# that answer it at one point are already on the box: every human table with as many pure-Stu boards (sAh) against every
# human table alone (hA), the nets alone, 4,000 deals, 4 workers beside round 4's training (a unit of its own, loop-human5).
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
cat > "$W/human5.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python
cd "$S"
play() {
  bash "$S/$T/run.sh" "$1" "$2" 131 30000 "$3" 4 || echo "$(date -u +%FT%TZ) job failed: $*" >> "$W/runs.log"
  "$PY" - "$W/runs/$1/results.jsonl" "$1" "$2" <<'PY' >> "$W/human.log" 2>&1
import json, sys, datetime
v = [json.loads(l)['common'] for l in open(sys.argv[1]) if l.strip()]
n = len(v); m = sum(v) / n; se = (sum((x - m) ** 2 for x in v) / (n - 1) / n) ** .5
print('%s MATCH %s %s: %+.3f +- %.3f IMPs a deal for the first bot (%d deals)' % (datetime.datetime.utcnow().strftime('%FT%TZ'), sys.argv[2], sys.argv[3], m, se, n))
PY
}
play xh-sAh-hA stusAh-n~stuhA-n 4000
EOS
sudo systemctl stop loop-human5 2>/dev/null || true; sudo systemctl reset-failed loop-human5 2>/dev/null || true
sudo systemd-run --unit=loop-human5 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/human5.sh"
sleep 20; systemctl is-active loop-human5 loop-r4 | tr '\n' ' '; tail -n 1 "$W/runs.log" | cut -c1-160; grep -o "\"epoch\": [0-9], \"seconds\": [0-9]*" $W/r4/net.log | tail -1

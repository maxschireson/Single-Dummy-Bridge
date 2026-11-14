# boxctl: timeout=120
# loop session: the experiment's second part, every expert table. A unit of its own (loop-human4): mini's set with every
# human table (m10A auctions as bid, m10B the unfamiliar ones blanked) and their matches; then from scratch at that size
# (hA every human table, bA as many pure-Stu boards, sAh both) and their matches.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
cat > "$W/human4.sh" <<'EOS'
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
if THREADS=8 bash "$T/exp_human.sh" all >> "$W/human.log" 2>&1; then
  play xh-m10A-n stum10A-n~stum10-n 4000
  play xh-m10B-n stum10B-n~stum10-n 4000
fi
if THREADS=8 bash "$T/exp_human.sh" big >> "$W/human.log" 2>&1; then
  play xh-hA-n stuhA-n~stubA-n 2000
  play xh-sAh-n stusAh-n~stubA-n 4000
fi
play xh-m10A-F stum10A-n~stum10F-n 4000
play xh-m10B-A stum10B-n~stum10A-n 4000
EOS
sudo systemctl stop loop-human4 2>/dev/null || true; sudo systemctl reset-failed loop-human4 2>/dev/null || true
sudo systemd-run --unit=loop-human4 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/human4.sh"
sleep 40; systemctl is-active loop-human loop-human3 loop-human4 | tr '\n' ' '; grep "stage all\|set human_unfit\|failed" "$W/human.log" | tail -n 3 | cut -c1-200; grep MATCH "$W/human.log" | tail -n 2 | cut -c1-170; date -u +%T

# boxctl: timeout=120
# loop session: the experiment's first nets-alone matches were close for the fine-tuned nets (+0.18 +- 0.09, +0.16 +- 0.08 at
# 2,000 deals), so the three run on to more deals in a unit of their own (loop-human2, 4 workers) beside the training.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
cat > "$W/human2.sh" <<'EOS'
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
play xh-mf-n stumf-n~stubf-n 8000
play xh-hf-n stuhf-n~stubf-n 8000
play xh-hs-n stuhs-n~stubs-n 4000
EOS
sudo systemctl stop loop-human2 2>/dev/null || true; sudo systemctl reset-failed loop-human2 2>/dev/null || true
sudo systemd-run --unit=loop-human2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/human2.sh"
sleep 20; systemctl is-active loop-human loop-human2 | tr '\n' ' '; tail -n 1 "$W/runs.log" | cut -c1-150; grep "stage\|net m\|failed" "$W/human.log" | tail -3 | cut -c1-200

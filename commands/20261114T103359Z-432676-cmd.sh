# boxctl: timeout=150
# loop session: the experiment's second part. Source to bd4d0b8 (new bots and stages; the running matches read the same files).
# The from-scratch medium nets s10 and s10h were kept at the epoch their held-out log-loss chose (1 and 2: the least trained,
# and not the same for both), so the match xh-s10h-n is void: both are replaced by their last epoch (6) and replayed as
# xh-s10h-n6. A unit of its own (loop-human3, 4 workers): every familiar-auction human table on mini's set (m10F), its
# match, the replay, and more deals for the two medium matches.
set -euo pipefail
COMMIT=bd4d0b82aded9c4f96f9aa22d34c247db979718f
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; X=$W/exp-human; P=$W/pub/exp-human; OUT=$S/models/cardplay/stu-exp-human-20261114
grep -q "end xh-s10h-n" "$W/runs.log" || { echo "xh-s10h-n still playing; try again"; exit 1; }
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
for t in s10 s10h; do cp -f "$X/$t/policy_epoch6.npz" "$OUT/$t.npz"; sha256sum "$OUT/$t.npz" | cut -c1-64 > "$P/$t/policy.sha256"
  echo "$(date -u +%FT%TZ) net $t replaced by its last epoch (6): sha256 $(cut -c1-16 "$P/$t/policy.sha256"); the match xh-s10h-n (epochs 1 and 2) is void" | tee -a "$P/timeline.log"; done
cat > "$W/human3.sh" <<'EOS'
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
play xh-s10h-n6 stus10h-n~stus10-n 2000
THREADS=4 bash "$T/exp_human.sh" fit >> "$W/human.log" 2>&1 && play xh-m10F-n stum10F-n~stum10-n 4000
play xh-m10h4-n stum10h4-n~stum10-n 6000
play xh-m10h-n stum10h-n~stum10-n 6000
EOS
sudo systemctl stop loop-human3 2>/dev/null || true; sudo systemctl reset-failed loop-human3 2>/dev/null || true
sudo systemd-run --unit=loop-human3 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/human3.sh"
sleep 15; systemctl is-active loop-human loop-human2 loop-human3 | tr '\n' ' '; grep MATCH "$W/human.log" | tail -n 4 | cut -c1-170; tail -n 3 "$W/runs.log" | cut -c1-150; date -u +%T

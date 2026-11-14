# boxctl: timeout=240
# loop session (Max, 09:25 to 09:45 UTC on 14 November: do the USBC's human boards belong in training? "you can take a machine"):
# azure5's collection (Gen 8's personalities' self-play, sg8t1) pauses; the source moves to b4e1eae; a unit of its own
# (loop-human) trains the experiment's nets (exp_human.sh) and plays them, each stage's nets as soon as they exist; then the
# source goes back to 9f18993 and the collection resumes where it stopped. Returns at once.
set -euo pipefail
COMMIT=b4e1eaef0c12160b2f74511bd14a95494532b6a0; BACK=9f1899325815367516ae38bb62c015d22c43d9e4
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
sudo systemctl stop loop-collect loop-collect-b loop-human 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; sleep 5
echo "sg8t1 so far: $(wc -l < "$W/runs/sg8t1/results.jsonl" 2>/dev/null || echo 0) tables"
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "$(date -u +%FT%TZ) azure5 lent to the human-boards experiment (Max, 09:37 UTC: 'you can take a machine'); the collection (jobs-azure5.txt, at sg8t1) pauses and resumes after it" >> "$W/runs.log"
cat > "$W/human.sh" <<'EOS'
#!/usr/bin/env bash
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python
cd "$S"
play() {   # NAME PAIR DEALS: a match on the gate's seed from deal 30000 (in no collection and no earlier match), then its score by deal
  bash "$S/$T/run.sh" "$1" "$2" 131 30000 "$3" 8 || echo "$(date -u +%FT%TZ) job failed: $*" >> "$W/runs.log"
  "$PY" - "$W/runs/$1/results.jsonl" "$1" "$2" <<'PY' >> "$W/human.log" 2>&1
import json, sys, datetime
v = [json.loads(l)['common'] for l in open(sys.argv[1]) if l.strip()]
n = len(v); m = sum(v) / n; se = (sum((x - m) ** 2 for x in v) / (n - 1) / n) ** .5
print('%s MATCH %s %s: %+.3f +- %.3f IMPs a deal for the first bot (%d deals)' % (datetime.datetime.utcnow().strftime('%FT%TZ'), sys.argv[2], sys.argv[3], m, se, n))
PY
}
stage() { THREADS=8 bash "$T/exp_human.sh" "$@" >> "$W/human.log" 2>&1; }
stage e1 || exit 1
play xh-hf-n stuhf-n~stubf-n 2000
play xh-mf-n stumf-n~stubf-n 2000
play xh-hs-n stuhs-n~stubs-n 2000
if stage mini; then
  play xh-m10h-n stum10h-n~stum10-n 2000
  play xh-m10h4-n stum10h4-n~stum10-n 2000
  if stage scratch; then play xh-s10h-n stus10h-n~stus10-n 2000; fi
fi
# inside the one-net rollout bot, in the order of what they decide
[ -s models/cardplay/stu-exp-human-20261114/m10h4.npz ] && play xh-m10h4-p stum10h4-pst~stum10-pst 250
play xh-hs-p stuhs-pst~stubs-pst 250
play xh-hf-p stuhf-pst~stubf-pst 250
[ -s models/cardplay/stu-exp-human-20261114/s10h.npz ] && play xh-s10h-p stus10h-pst~stus10-pst 250
[ -s models/cardplay/stu-exp-human-20261114/m10h.npz ] && play xh-m10h-p stum10h-pst~stum10-pst 250
echo "$(date -u +%FT%TZ) the human-boards experiment's matches are played; the collection resumes" >> "$W/runs.log"
git -C "$S" checkout -q 9f1899325815367516ae38bb62c015d22c43d9e4
sudo systemctl reset-failed loop-collect 2>/dev/null
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure5.txt"
EOS
chmod +x "$W/human.sh"; : > "$W/human.log"
cd "$S" && THREADS=8 bash "$T/exp_human.sh" sets 2>&1 | tail -n 8
sudo systemctl reset-failed loop-human 2>/dev/null || true
sudo systemd-run --unit=loop-human --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$W/human.sh"
sleep 45; echo "units: $(for u in loop-collect loop-human loop-publish; do printf '%s=%s ' $u $(systemctl is-active $u); done)"; tail -n 5 "$W/human.log" | cut -c1-250; tail -n 3 "$W/exp-human/hf.log" 2>/dev/null | cut -c1-250; date -u +%FT%TZ

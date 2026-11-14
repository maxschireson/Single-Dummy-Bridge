# boxctl: timeout=900
# loop session (Max, 21:38 UTC: "please keep this thread moving one way or the other"): H05's reliability run (#37), first a
# 12-pair check of bench/pair_reliability.py on sp3s (round 3's one-net self-play records, here), from the second checkout at
# f56a462, 4 workers at Nice 10 beside the width run. If it works, a unit (loop-pairs) runs 3,000 pairs (about 20 minutes).
set -uo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; COMMIT=f56a46227adc348c813985c875e5d15ffc970207
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q -f "$COMMIT"; git -C "$S2" log -1 --format='source %h'
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
time timeout 600 nice -n 10 "$PY" training/rollout-loop-20261113/bench/pair_reliability.py "$W/runs/sp3s" --source "$W/capsule/recovery" --pairs 12 --per-record 3 --workers 4 --out /tmp/pairs-test.jsonl 2>&1 | grep -v Warning | tail -12 | cut -c1-220
head -c 600 /tmp/pairs-test.jsonl; echo; wc -l < /tmp/pairs-test.jsonl

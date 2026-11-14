# boxctl: timeout=300
# loop session: H05's reliability run (#37; loop took it at 21:50 UTC to keep the thread moving, Max 21:38). Unit loop-pairs:
# bench/pair_reliability.py at e590369 on 2,500 recorded pairs from sp3s (round 3's self-play) and then 2,500 from sp0, 128
# fresh layouts each from the fork seat's own information, 4 workers at Nice 10 beside the width run (about 10 minutes each).
# Rows and reports to pub/h05/ for the publisher. Read-only on the episodes.
set -uo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; COMMIT=e590369ada31fe93667e4b7f5ccf7c204142e323
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q -f "$COMMIT"; git -C "$S2" log -1 --format='source %h'
mkdir -p "$W/pub/h05"; ls -d "$W/runs/sp3s" "$W/runs/sp0" 2>&1
cat > "$W/pairs.sh" <<EOS
#!/usr/bin/env bash
cd $S2; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for run in sp3s sp0; do
  rm -f $W/pub/h05/pairs-\$run.jsonl
  nice -n 10 $PY training/rollout-loop-20261113/bench/pair_reliability.py $W/runs/\$run --source $W/capsule/recovery --pairs 2500 --per-record 3 --workers 4 --seed 5 --out $W/pub/h05/pairs-\$run.jsonl 2>&1 | grep -v Warning > $W/pub/h05/report-\$run.txt
done
$PY training/rollout-loop-20261113/bench/pair_reliability.py x --report $W/pub/h05/pairs-sp3s.jsonl $W/pub/h05/pairs-sp0.jsonl > $W/pub/h05/report-both.txt 2>&1
EOS
sudo systemctl stop loop-pairs 2>/dev/null; sudo systemctl reset-failed loop-pairs 2>/dev/null
sudo systemd-run --unit=loop-pairs --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" -p RuntimeMaxSec=3600 -- bash "$W/pairs.sh"
sleep 60; systemctl is-active loop-pairs; wc -l "$W"/pub/h05/*.jsonl 2>/dev/null; cat "$W"/pub/h05/report-sp3s.txt 2>/dev/null | head -3
tail -2 "$W/exp-width/w1536.log" 2>/dev/null | cut -c1-160

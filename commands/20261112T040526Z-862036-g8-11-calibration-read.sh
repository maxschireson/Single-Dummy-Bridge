# boxctl: timeout=5400
# boxctl: timeout=5400
# g8: how much the policy net's reading of each opponent type's cards tells about the hidden hands (nats, by exponent).
# Waits for the seven calibration matches, then reads them in parallel at low priority while the queue goes on.
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
for i in $(seq 1 240); do grep -q "end k-trandom" "$G/queue.log" 2>/dev/null && break; sleep 10; done
grep -q "end k-trandom" "$G/queue.log" || { echo "the calibration matches have not finished"; tail -3 "$G/queue.log"; exit 1; }
cd "$G/src" || exit 1
for t in 7s 6 5rz 1 thigh tlow trandom; do
  OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 nice -n 5 "$PY" scripts/gen8_play_info.py --source "$CAP" --bots configs/gen8-proto-bots.json --bot 8s-32 \
    --mover candidate --until 12 --tables 128 --out "$G/runs/k-$t/play_info.json" "$G/runs/k-$t/episodes" > "$G/runs/k-$t.info.log" 2>&1 &
done
wait
for t in 7s 6 5rz 1 thigh tlow trandom; do
  echo "== 8s-32 reading $t ($(grep -o '"boards": [0-9]*' "$G/runs/k-$t/summary.json" | head -1), $(grep -o '"imps_per_board": [-0-9.]*' "$G/runs/k-$t/summary.json" | head -1))"
  grep -E "^gain|^ +all|declarer|defender|opponents' plays|partner's plays|decisions in" "$G/runs/k-$t.info.log" | cut -c1-150
  grep -E "Error|Traceback" "$G/runs/k-$t.info.log" | head -2
done

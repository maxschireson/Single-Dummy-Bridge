# boxctl: timeout=2400
# boxctl: timeout=2400
# loop session: the trainer's new --select on round 2's own rows (already built under ~/work/loop/r2): six epochs at most,
# the epoch best on pure Stu's held-out cards with the other bots' log-loss within 0.02 of the start. Four threads at
# Nice 10 beside the collection. The checkout changes the trainer and round2.sh only; the chains are not stopped.
set -euo pipefail
COMMIT=e5f249daed3ab2b6c35be7aad7f038f71e035265
W=$HOME/work/loop; S=$W/src; PY=$W/venv/bin/python; R=$W/r2
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" | tail -3
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'; cd "$S"
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4
nice -n 10 "$PY" scripts/train_rollout_net.py --data "$R/train.npz" --all-train --val-data "$R/val.npz" --out "$R/sel" --width 768   --epochs 6 --patience 2 --batch 256 --lr 1e-4 --id-dropout 0 --init "$W/pub/train-r1/policy.npz" --init-as stup0=stu0 --select stup0 --forget 0.02 > "$R/sel.log" 2>&1   || { echo "training failed"; tail -n 8 "$R/sel.log"; exit 1; }
grep '"select"' "$R/sel.log" | cut -c1-260
"$PY" - "$R" <<'PY'
import json, sys
R = sys.argv[1]; m = json.load(open(R + '/sel/metrics.json')); v = m['validation']
print('selected epoch', m['selected_epoch'])
ph = v['by_bot_phase']['stup0']
print('stup0 first card gives up:', {p: ph[p]['regret'] for p in ph}, '| value head:', {p: ph[p]['regret_gap_head'] for p in ph})
print('log-loss stup0 %.4f | 8s-32 %.4f | all %.4f' % (v['by_bot']['stup0']['nll'], v['by_bot']['8s-32']['nll'], v['all']['nll']))
PY
for r in sp0 spr0; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables"; done; systemctl is-active loop-collect loop-collect-b | tr '\n' ' '; date -u +%FT%TZ

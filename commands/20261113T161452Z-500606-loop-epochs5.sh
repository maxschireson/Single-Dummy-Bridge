# boxctl: timeout=1500
# boxctl: timeout=1500
# loop session: round 2's later epochs scored on the same held-out rows (the trainer picked epoch 1 by the loss over
# every bot's rows): does more training lower what pure Stu's first card gives up? Two threads at Nice 10 beside the rungs.
set -euo pipefail
W=$HOME/work/loop; S=$W/src; PY=$W/venv/bin/python; R=$W/r2; cd "$S"
export OPENBLAS_NUM_THREADS=2 OMP_NUM_THREADS=2 MKL_NUM_THREADS=2
ls "$R/net" | tr '\n' ' '; echo
for e in 2 3; do
  [ -f "$R/net/policy_epoch$e.npz" ] || continue
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$R/train.npz" --all-train --val-data "$R/val.npz" --out "$R/eval$e" --width 768 \
    --epochs 1 --batch 256 --lr 1e-12 --id-dropout 0 --init "$R/net/policy_epoch$e.npz" > "$R/eval$e.log" 2>&1 || { echo "eval $e failed"; tail -n 3 "$R/eval$e.log"; }
done
"$PY" - "$R" <<'PY'
import json, sys, os
R = sys.argv[1]
runs = [('before', R + '/before/metrics.json'), ('epoch 1', R + '/net/metrics.json')] + [(f'epoch {e}', f'{R}/eval{e}/metrics.json') for e in (2, 3) if os.path.exists(f'{R}/eval{e}/metrics.json')]
M = [(n, json.load(open(p))['validation']) for n, p in runs]
print('%-9s | %-31s | %-31s | %s' % ('', 'stup0 first card gives up', 'stup0 value head gives up', 'log-loss stup0 / 8s-32 / all'))
print('%-9s | %-31s | %-31s |' % ('', 'lead   t1-4   t5-8   t9-13', 'lead   t1-4   t5-8   t9-13'))
for n, v in M:
    ph = v['by_bot_phase']['stup0']
    g = lambda k: ' '.join('%.4f' % ph[p][k] for p in ('lead', 'tricks 1-4', 'tricks 5-8', 'tricks 9-13'))
    print('%-9s | %s | %s | %.4f / %.4f / %.4f' % (n, g('regret'), g('regret_gap_head'), v['by_bot']['stup0']['nll'], v['by_bot']['8s-32']['nll'], v['all']['nll']))
PY
tail -n 2 "$W/runs.log" | cut -c1-120; date -u +%FT%TZ

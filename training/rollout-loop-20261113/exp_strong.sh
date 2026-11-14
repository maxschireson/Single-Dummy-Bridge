#!/usr/bin/env bash
# Max, 02:26 UTC on 14 November: "build a new net from data on just the strongest bots, vs a net on the same distribution
# of bot strength we are using now at the same size". From rollout net v2's own set (the plan session's, 30.4 million
# rows of 75,409 deals): STRONG = every row Gen 8 card play decided (8s-32 and 8c-32, about 3.7 million); MIX = whole
# deals drawn at random until as many rows, so the bots in v2's proportions. Each net trained from scratch on v2's
# recipe (5 epochs, rate 2e-3 falling by one cosine, batch 512, bot vectors with 15% id dropout) at each of WIDTHS (512
# and 768: a set a quarter the size of v4.1's may want a narrower net; Max, 02:28 UTC), the epoch kept on v2's held-out
# set (freshB). Writes ~/work/loop/exp-strong/, copies the nets and scores to pub/exp-strong/.
#   THREADS=8 bash training/rollout-loop-20261113/exp_strong.sh
set -euo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python; T=training/rollout-loop-20261113; X=$W/exp-strong; P=$W/pub/exp-strong
BIG=${BIG:-$HOME/work/plan/rnet2w/data/train.npz}; FRESH=${FRESH:-$HOME/work/plan/rnet2w/data/freshB.npz}
V2=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz
THREADS=${THREADS:-8}; WIDTHS=${WIDTHS:-512 768}
cd "$(dirname "$0")/../.."
rm -rf "$X"; mkdir -p "$X" "$P"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$P/timeline.log"; }
say "start; source $(git rev-parse --short HEAD); threads $THREADS"
nice -n 10 "$PY" $T/sample_set.py "$BIG" "$X/strong.npz" --rows 100000000 --bots 8s-32,8c-32 | tee -a "$P/timeline.log"
N=$("$PY" -c "import numpy as np, sys; print(len(np.load(sys.argv[1], mmap_mode='r')['deal']))" "$X/strong.npz")
nice -n 10 "$PY" $T/sample_set.py "$BIG" "$X/mix.npz" --rows "$N" --seed 3 | tee -a "$P/timeline.log"
export OPENBLAS_NUM_THREADS=$THREADS OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS
for width in $WIDTHS; do for data in strong mix; do net=$data-$width
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$X/$data.npz" --all-train --val-data "$FRESH" --out "$X/$net" --kind suit --width "$width" \
    --epochs 5 --batch 512 --lr 2e-3 --save-epochs --compare "$V2" > "$X/$net.log" 2>&1 || { say "training $net failed: $(tail -n 2 "$X/$net.log" | tr '\n' ' ' | cut -c1-200)"; exit 1; }
  mkdir -p "$P/$net"; cp -f "$X/$net/policy.npz" "$X/$net/metrics.json" "$X/$net.log" "$P/$net/"
  sha256sum "$X/$net/policy.npz" | cut -c1-64 > "$P/$net/policy.sha256"
  say "trained $net: sha256 $(cut -c1-16 "$P/$net/policy.sha256"), selected epoch $(grep -o '"selected_epoch": [0-9]*' "$X/$net/metrics.json" | grep -o '[0-9]*$')"
done; done
"$PY" - "$X" <<'PY' | tee -a "$P/timeline.log"
import json, sys
X = sys.argv[1]
import glob, os
for d in sorted(glob.glob(f'{X}/*/metrics.json')):
    net = os.path.basename(os.path.dirname(d)); m = json.load(open(d)); v = m['validation']
    print(net, 'epochs (held-out log-loss):', [round(h['val']['nll'], 4) for h in m.get('history', [])])
    by = v['by_bot']
    print(net, 'held-out log-loss all %.4f | exact card %.4f | regret %s' % (v['all']['nll'], v['all']['agree'], v['all'].get('regret')),
          '| 8s-32 nll %.4f | 6-32 nll %s' % (by.get('8s-32', {}).get('nll', float('nan')), by.get('6-32', {}).get('nll')))
    for path, c in (m.get('compared') or {}).items():
        print('   v2 on the same rows: log-loss %.4f, exact card %.4f, regret %s' % (c['all']['nll'], c['all']['agree'], c['all'].get('regret')))
PY
say "done"

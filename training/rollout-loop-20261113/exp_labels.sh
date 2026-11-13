#!/usr/bin/env bash
# Two experiments on one box's own collection records, beside its collection (Max, 22:26 and 22:31 UTC on 13 November):
#   bash training/rollout-loop-20261113/exp_labels.sh RUN[,RUN...]
#  - label quality against volume: the rows rebuilt with the labels of a bot that had only the first 8, 16 or 32 of the
#    recorded layouts of each rollout decision (gen7_build_dataset --rollout-layouts: each candidate's deficit over those
#    layouts, and the card the policy learns is the one best over them); trained on the same tables as the full labels;
#  - tables against positions: every decision of half the tables against a random half of the decisions of all of them
#    (the same number of rows);
#  - and the learning curve on the same tables (a quarter, a half, all of them, full labels) to read both in tables.
# Every net starts from round 1's (stup0 from stu0), trains 3 epochs at 1e-4 on the train split of RUN's tables (no
# replay rows: only pure Stu's choices are scored) and keeps the epoch best on pure Stu's held-out log-loss. All are
# scored on the same held-out rows: the validation split of every row block and cut file the boxes have published
# (full labels), by regret_pairs.py (paired, SE by deal), the policy's first card and the value head's.
# Writes ~/work/loop/exp/ and copies the scores and logs to ~/work/loop/pub/exp/ for the publisher. Nice 10, THREADS.
set -euo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python; T=training/rollout-loop-20261113; X=$W/exp; P=$W/pub/exp
SCORER=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
R1=models/cardplay/stu-net-r1-20261113/policy.npz
M=training/rollout-net-v2-20261113/merge_sets.py
THREADS=${THREADS:-4}
cd "$(dirname "$0")/../.."
rm -rf "$X"; mkdir -p "$X/eps" "$X/val" "$P"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$P/timeline.log"; }
say "start; source $(git rev-parse --short HEAD); runs $1; threads $THREADS"
export OPENBLAS_NUM_THREADS=$THREADS OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS

# 1. The runs' finished records, and their rows with the shortened labels beside the full ones.
for run in ${1//,/ }; do
  find "$W/runs/$run/episodes" -name '*.json.gz' -mmin +1 | while read -r f; do ln -f "$f" "$X/eps/$run-$(basename "$f")"; done
done
say "$(ls "$X/eps" | wc -l) records"
nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes "$X/eps" --scorer "$SCORER" --out "$X/all.npz" --workers "$THREADS" --policy-only \
  --rollout-gap --rollout-layouts 8,16,32 --alias "$(cat $T/alias.txt)" 2>&1 | tail -n 1 | tee -a "$P/timeline.log"

# 2. The held-out rows: the validation split of every published block and cut file (this box's own from pub/).
CUT=1 bash $T/fetch_rows.sh azure1 azure2 azure3 azure6 > /dev/null
nice -n 10 "$PY" - "$X/val" "$W"/pub/rows/*.npz "$W"/pub/rows-cut/*.npz "$W"/in/rows-azure*/*.npz "$W"/in/cut-azure*/*.npz <<'PY'
import sys, hashlib
from pathlib import Path
import numpy as np
out, seen = Path(sys.argv[1]), set()
for f in sys.argv[2:]:
    p = Path(f)
    if not p.exists() or p.name in seen:
        continue
    seen.add(p.name)
    with np.load(p, allow_pickle=True) as z:
        d = {k: z[k] for k in z.files}
    keep = d['deal_split'][d['deal']] == 1
    if not keep.any():
        continue
    for k in ('state', 'order', 'legal', 'ctx', 'auction', 'shown', 'gap', 'owner', 'meta', 'deal'):
        d[k] = d[k][keep]
    np.savez(out / p.name, **d)
print(len(list(out.glob('*.npz'))), 'files with validation rows')
PY
nice -n 10 "$PY" $M "$X/val.npz" "$X"/val/*.npz | tee -a "$P/timeline.log"

# 3. The variants and their nets.
nice -n 10 "$PY" $T/label_variant.py "$X/all.npz" "$X/full.npz" | tee -a "$P/timeline.log"
for k in 32 16 8; do nice -n 10 "$PY" $T/label_variant.py "$X/all.npz" "$X/k$k.npz" --k $k | tee -a "$P/timeline.log"; done
nice -n 10 "$PY" $T/label_variant.py "$X/all.npz" "$X/halfrows.npz" --rows 0.5 --seed 7 | tee -a "$P/timeline.log"
rm -f "$X/all.npz"
train() {   # name data fraction
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$X/$2.npz" --val-data "$X/val.npz" --out "$X/$1" --width 768 --epochs 3 --patience 0 \
    --batch 256 --lr 1e-4 --id-dropout 0 --init "$R1" --init-as stup0=stu0 --select stup0 --forget 10 --fraction "$3" > "$X/$1.log" 2>&1 \
    || { say "training $1 failed: $(tail -n 2 "$X/$1.log" | tr '\n' ' ' | cut -c1-200)"; return 0; }
  say "trained $1 ($2, fraction $3): $(grep -o '"selected_epoch": [0-9]*' "$X/$1/metrics.json" 2>/dev/null)"
}
mkdir -p "$X/start"; ln -sf "$PWD/$R1" "$X/start/policy.npz"     # the start: round 1's net (regret_pairs reads stup0 as stu0)
train full full 1
train half-tables full 0.5
train quarter-tables full 0.25
train half-rows halfrows 1
train k32 k32 1
train k16 k16 1
train k8 k8 1

# 4. Scores: each against all tables with full labels, and the curve against the start.
for head in policy value; do
  for pair in "start full" "quarter-tables full" "half-tables full" "half-rows full" "half-rows half-tables" "k32 full" "k16 full" "k8 full" \
              "k16 half-tables" "k8 quarter-tables"; do
    set -- $pair
    [ -f "$X/$1/policy.npz" ] && [ -f "$X/$2/policy.npz" ] || continue
    echo "== $head head: $1 -> $2" | tee -a "$P/scores.txt"
    nice -n 10 "$PY" $T/regret_pairs.py "$X/val.npz" "$X/$1/policy.npz" "$X/$2/policy.npz" --head $head --json "$P/$head-$1-$2.json" | tee -a "$P/scores.txt" || true
  done
done
for n in start full half-tables quarter-tables half-rows k32 k16 k8; do [ -f "$X/$n/metrics.json" ] && cp -f "$X/$n/metrics.json" "$P/metrics-$n.json"; done
say "done"

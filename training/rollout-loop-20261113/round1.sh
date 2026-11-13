#!/usr/bin/env bash
# Round 1's net on the collecting box, quick variant (PLAN.md): Stu's rows so far with as many rows again of the bots the
# net already knows, a few epochs from rollout net v2 at a low rate, scored on held-out Stu boards and on the other bots'
# held-out boards (what it forgets).
#   bash training/rollout-loop-20261113/round1.sh [NAME=r1] [HELD=250] [EPOCHS=4] [LR=3e-4]
# Run from a checkout of this branch with ~/work/loop set up (README). Reads, never writes: the collection's records
# (hard links), and the plan session's warm-run set and held-out set (BIG, FRESH). Runs at Nice 10 on THREADS threads.
# Writes ~/work/loop/NAME and copies the net, its scores and logs to ~/work/loop/pub/train-NAME for the publisher.
set -euo pipefail
NAME=${1:-r1}; HELD=${2:-250}; EPOCHS=${3:-4}; LR=${4:-3e-4}
W=$HOME/work/loop; PY=$W/venv/bin/python; T=training/rollout-loop-20261113; M=training/rollout-net-v2-20261113/merge_sets.py
BIG=${BIG:-$HOME/work/plan/rnet2w/data/train.npz}; FRESH=${FRESH:-$HOME/work/plan/rnet2w/data/freshB.npz}
THREADS=${THREADS:-4}
V2=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz
V41=models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz
V1=models/cardplay/rollout-net-v1-20261113/policy_ft.npz
SCORER=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
ALIAS=stu0a=stu0,stu0b=stu0,z0a-v2=stu0,z0b-v2=stu0
cd "$(dirname "$0")/../.."
R=$W/$NAME; rm -rf "$R"; mkdir -p "$R/train" "$R/held"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/timeline.log"; }
say "start $NAME; source $(git rev-parse --short HEAD); held out $HELD boards; $EPOCHS epochs at $LR"

# 1. Records: every finished board of this box's collection; the HELD most recent boards of run s0 are held out.
find "$W/runs/s0/episodes" -name '*.json.gz' -mmin +1 | sort > "$R/s0.txt"
n=$(wc -l < "$R/s0.txt")
[ "$n" -gt $((HELD + 100)) ] || { say "only $n records in s0"; exit 1; }
head -n $((n - HELD)) "$R/s0.txt" | xargs -I{} ln {} "$R/train/"
tail -n "$HELD" "$R/s0.txt" | xargs -I{} ln {} "$R/held/"
for f in "$W"/runs/r0/episodes/*.json.gz; do [ -e "$f" ] && ln "$f" "$R/train/r0-$(basename "$f")"; done
if [ -d "$W/in/s0b" ]; then for f in "$W"/in/s0b/*.json.gz; do ln "$f" "$R/train/s0b-$(basename "$f")"; done; fi    # the other box's shard, once moved here
say "records: $(ls "$R/train" | wc -l) to train on, $(ls "$R/held" | wc -l) held out"

# 2. Rows.
for part in train held; do
  nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes "$R/$part" --scorer "$SCORER" --out "$R/stu_$part.npz" --workers "$THREADS" \
    --policy-only --rollout-gap --alias "$ALIAS" 2>&1 | tail -1 | tee -a "$R/timeline.log"
done

# 3. As many rows again of the bots the net knows; the joined training set; the joined held-out set.
rows=$("$PY" -c "import numpy as np, sys; print(len(np.load(sys.argv[1])['deal']))" "$R/stu_train.npz")
nice -n 10 "$PY" $T/sample_set.py "$BIG" "$R/replay.npz" --rows "$rows" --seed 1 | tee -a "$R/timeline.log"
nice -n 10 "$PY" $M "$R/train.npz" "$R/stu_train.npz" "$R/replay.npz" | tee -a "$R/timeline.log"
nice -n 10 "$PY" $M "$R/val.npz" "$R/stu_held.npz" "$FRESH" | tee -a "$R/timeline.log"

# 4. The net before (Stu's vectors are 8s-32's and nothing is trained: a rate of 1e-12) and after, on the same held-out rows.
export OPENBLAS_NUM_THREADS=$THREADS OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS
train() {   # folder epochs rate
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$R/train.npz" --all-train --val-data "$R/val.npz" --out "$R/$1" --width 768 \
    --epochs "$2" --patience 2 --batch 256 --lr "$3" --id-dropout 0 --save-epochs --init "$V2" --init-as stu0=8s-32 \
    --compare "$V2" --compare "$V41" --compare "$V1" > "$R/$1.log" 2>&1 || { say "training $1 failed"; tail -n 5 "$R/$1.log"; exit 1; }
}
train before 1 1e-12
train net "$EPOCHS" "$LR"
say "trained"

# 5. Scores, bot by bot, before and after.
"$PY" - "$R" <<'PY' | tee -a "$R/timeline.log"
import json, sys
R = sys.argv[1]
b, a = json.load(open(R + '/before/metrics.json')), json.load(open(R + '/net/metrics.json'))
print('epochs:', [(h['epoch'], h['val']['nll'], h['val']['agree']) for h in a['history']], '| selected', a['selected_epoch'])
print('%-8s %7s | %-17s | %-17s | %-23s' % ('bot', 'rows', 'log-loss', 'exact card', 'tricks given up (rated)'))
vb, va = b['validation']['by_bot'], a['validation']['by_bot']
for bot in sorted(vb, key=lambda k: -vb[k]['n']):
    x, y = vb[bot], va[bot]
    print('%-8s %7d | %.4f -> %.4f | %.4f -> %.4f | %s -> %s' % (bot, x['n'], x['nll'], y['nll'], x['agree'], y['agree'], x.get('regret'), y.get('regret')))
for key in ('all', 'from_trick_7'):
    x, y = b['validation'][key], a['validation'][key]
    print('%-12s log-loss %.4f -> %.4f | exact card %.4f -> %.4f' % (key, x['nll'], y['nll'], x['agree'], y['agree']))
print('no bot named (all rows): log-loss %.4f -> %.4f' % (b['who_use']['blank']['all']['nll'], a['who_use']['blank']['all']['nll']))
PY

# 6. For the publisher (and the dashboard: train-NAME/metrics.json is the trainer's own file, one record an epoch under `history`).
P=$W/pub/train-$NAME; mkdir -p "$P"
cp -f "$R/net/metrics.json" "$R/net/policy.npz" "$R/net.log" "$R/before.log" "$R/timeline.log" "$P/"
cp -f "$R/before/metrics.json" "$P/metrics_before.json"
sha256sum "$R/net/policy.npz" | cut -c1-64 > "$P/policy.sha256"
say "published to $P: policy.npz sha256 $(cut -c1-16 "$P/policy.sha256")"

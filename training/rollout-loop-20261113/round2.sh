#!/usr/bin/env bash
# A later round's net on the collecting box (PLAN.md): pure Stu's rows so far (every rollout decision with its
# candidates' values, the opening lead with a value for all 13 cards where it was rolled out), with REPLAY times as many
# rows of the bots the net already knows, a few epochs from the last round's net at a low rate; scored on held-out boards
# of the first run and on the other bots' held-out boards (what it forgets).
#   bash training/rollout-loop-20261113/round2.sh [NAME=r2] [RUNS=spr0,sp0] [HELD=150] [EPOCHS=4] [LR=1e-4]
# RUNS: collection runs under ~/work/loop/runs, the first one's HELD most recent boards held out. Pure Stu's rows are
# named `stup0` (its ids are aliased to it); the net starts with Stu's vectors for it (INIT is round 1's net, which
# has `stu0`). Run from a checkout of this branch with ~/work/loop set up (README). Reads, never writes: the
# collection's records (hard links), and the plan session's warm-run set and held-out set (BIG, FRESH). Runs at Nice 10
# on THREADS threads. Writes ~/work/loop/NAME and copies the net, its scores and logs to ~/work/loop/pub/train-NAME.
# EXTRA: more row files to train on, e.g. other boxes' blocks fetched by fetch_rows.sh ("$HOME"/work/loop/in/rows-*/*.npz).
# SELECT, FORGET: the trainer's --select and --forget (e.g. SELECT=stup0 FORGET=0.02: the epoch that is best on pure
# Stu's held-out cards among those that leave the other bots' log-loss within 0.02 of the starting net's). Without
# SELECT the epoch with the lowest log-loss over every bot's rows is kept, which is the least-trained one here.
# Later rounds use this script too: each trains from INIT on every table so far, not from the round before.
set -euo pipefail
NAME=${1:-r2}; RUNS=${2:-spr0,sp0}; HELD=${3:-150}; EPOCHS=${4:-4}; LR=${5:-1e-4}
REPLAY=${REPLAY:-1}
W=$HOME/work/loop; PY=$W/venv/bin/python; T=training/rollout-loop-20261113; M=training/rollout-net-v2-20261113/merge_sets.py
BIG=${BIG:-$HOME/work/plan/rnet2w/data/train.npz}; FRESH=${FRESH:-$HOME/work/plan/rnet2w/data/freshB.npz}
THREADS=${THREADS:-4}
V2=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz
V41=models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz
V1=models/cardplay/rollout-net-v1-20261113/policy_ft.npz
SCORER=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
ALIAS=$(cat "$(dirname "$0")/alias.txt")
EXTRA=${EXTRA:-}; SELECT=${SELECT:-}; FORGET=${FORGET:-0.02}
cd "$(dirname "$0")/../.."
R=$W/$NAME; rm -rf "$R"; mkdir -p "$R/train" "$R/held"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$R/timeline.log"; }
INIT=${INIT:-$W/pub/train-r1/policy.npz}
[ -f "$INIT" ] || { echo "no starting net at $INIT"; exit 1; }
say "start $NAME; source $(git rev-parse --short HEAD); runs $RUNS; held out $HELD boards; $EPOCHS epochs at $LR; replay x$REPLAY; from $INIT"

# 1. Records: every finished board of the runs; the HELD most recent boards of the first run are held out.
first=1
for run in ${RUNS//,/ }; do
  find "$W/runs/$run/episodes" -name '*.json.gz' -mmin +1 | sort > "$R/$run.txt"
  n=$(wc -l < "$R/$run.txt")
  if [ "$first" = 1 ]; then
    [ "$n" -gt $((HELD + 100)) ] || { say "only $n records in $run"; exit 1; }
    head -n $((n - HELD)) "$R/$run.txt" | while read -r f; do ln "$f" "$R/train/$run-$(basename "$f")"; done
    tail -n "$HELD" "$R/$run.txt" | while read -r f; do ln "$f" "$R/held/$run-$(basename "$f")"; done
    first=0
  else
    while read -r f; do ln "$f" "$R/train/$run-$(basename "$f")"; done < "$R/$run.txt"
  fi
  say "$run: $n records"
done
say "records: $(ls "$R/train" | wc -l) to train on, $(ls "$R/held" | wc -l) held out"

# 2. Rows.
for part in train held; do
  nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes "$R/$part" --scorer "$SCORER" --out "$R/stu_$part.npz" --workers "$THREADS" \
    --policy-only --rollout-gap --alias "$ALIAS" 2>&1 | tail -1 | tee -a "$R/timeline.log"
done

# 3. As many rows again of the bots the net knows; the joined training set; the joined held-out set.
# shellcheck disable=SC2086
rows=$("$PY" -c "import numpy as np, sys; print(int(sum(len(np.load(f)['deal']) for f in sys.argv[2:]) * float(sys.argv[1])))" "$REPLAY" "$R/stu_train.npz" $EXTRA)
[ -z "$EXTRA" ] || say "with $(echo $EXTRA | wc -w) more row files from other boxes"
nice -n 10 "$PY" $T/sample_set.py "$BIG" "$R/replay.npz" --rows "$rows" --seed 1 | tee -a "$R/timeline.log"
# shellcheck disable=SC2086
nice -n 10 "$PY" $M "$R/train.npz" "$R/stu_train.npz" $EXTRA "$R/replay.npz" | tee -a "$R/timeline.log"
nice -n 10 "$PY" $M "$R/val.npz" "$R/stu_held.npz" "$FRESH" | tee -a "$R/timeline.log"

# 4. The net before (pure Stu's vectors are Stu's and nothing is trained: a rate of 1e-12) and after, on the same held-out rows.
export OPENBLAS_NUM_THREADS=$THREADS OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS
train() {   # folder epochs rate
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$R/train.npz" --all-train --val-data "$R/val.npz" --out "$R/$1" --width 768 \
    --epochs "$2" --patience 2 --batch 256 --lr "$3" --id-dropout 0 --save-epochs --init "$INIT" --init-as stup0=stu0 \
    ${SELECT:+--select "$SELECT" --forget "$FORGET"} \
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
print('%-8s %7s | %-17s | %-17s | %-23s | %s' % ('bot', 'rows', 'log-loss', 'exact card', 'tricks given up (rated)', 'best rated card picked'))
vb, va = b['validation']['by_bot'], a['validation']['by_bot']
for bot in sorted(vb, key=lambda k: -vb[k]['n']):
    x, y = vb[bot], va[bot]
    print('%-8s %7d | %.4f -> %.4f | %.4f -> %.4f | %s -> %s | %s -> %s' % (bot, x['n'], x['nll'], y['nll'], x['agree'], y['agree'], x.get('regret'), y.get('regret'), x.get('rated_pick'), y.get('rated_pick')))
for key in ('all', 'from_trick_7'):
    x, y = b['validation'][key], a['validation'][key]
    print('%-12s log-loss %.4f -> %.4f | exact card %.4f -> %.4f' % (key, x['nll'], y['nll'], x['agree'], y['agree']))
print('no bot named (all rows): log-loss %.4f -> %.4f' % (b['who_use']['blank']['all']['nll'], a['who_use']['blank']['all']['nll']))
# Pure Stu by phase: tricks given up against its own rollouts' values by the net's first card, by the card its value
# head rates best, and by a random rated card. At the lead every card is rated where the lead was rolled out.
pb, pa = b['validation'].get('by_bot_phase', {}).get('stup0', {}), a['validation'].get('by_bot_phase', {}).get('stup0', {})
print('%-12s %6s %6s | %-19s | %-19s | %-19s | %s' % ('stup0', 'rows', 'rated', 'first card gives up', 'value head gives up', 'exact card', 'random rated card'))
for phase in pb:
    x, y = pb[phase], pa.get(phase, {})
    print('%-12s %6d %6d | %s -> %s | %s -> %s | %s -> %s | %s' % (phase, x['n'], x['searched'], x.get('regret'), y.get('regret'), x.get('regret_gap_head'), y.get('regret_gap_head'),
                                                              x.get('agree'), y.get('agree'), x.get('regret_random')))
PY

# 6. For the publisher (and the dashboard: train-NAME/metrics.json is the trainer's own file, one record an epoch under `history`).
P=$W/pub/train-$NAME; mkdir -p "$P"
cp -f "$R/net/metrics.json" "$R/net/policy.npz" "$R/net.log" "$R/before.log" "$R/timeline.log" "$P/"
cp -f "$R/before/metrics.json" "$P/metrics_before.json"
sha256sum "$R/net/policy.npz" | cut -c1-64 > "$P/policy.sha256"
say "published to $P: policy.npz sha256 $(cut -c1-16 "$P/policy.sha256")"

#!/usr/bin/env bash
# Max, 09:25 to 09:45 UTC on 14 November: do the USBC's human boards belong in training, and at what weight? "This is the
# big question"; "more value than a few thousand more of the same boards". The boards: adult USBCs of 2021 to 2023, one
# table a deal with an auction our bidder knows (usbc/human_episodes.py; 1,556 boards), the target the card the expert
# played. The 2025 USBCs and the juniors stay test data. Sets come from the feed branch (usbc/human_sets.py).
#
#   THREADS=8 bash training/rollout-loop-20261113/exp_human.sh STAGE [STAGE ...]
#
# sets     fetch the sets from FEED into ~/work/loop/exp-human
# e1       teacher against teacher, 1,556 boards each. From round 3's net, 4 epochs at 1e-4 (a round's recipe, no replay):
#          hf (human boards; the net's new bot `usbc` starts as pure Stu), bf (as many one-net SiD self-play boards), mf (both
#          together). From scratch (256 wide, up to 40 epochs, the epoch best on its own held-out deals): hs, bs.
# mini     round 4 in small: from round 1's net as a round trains (4 epochs at 1e-4, as many replay rows), on about 10,000
#          pure-Stu boards (m10), with the human boards (m10h), and with them four times over (m10h4).
# scratch  from scratch on the same 10,000 boards (s10) and with the human boards (s10h): 512 wide, 6 epochs at 2e-3.
# Every net is scored on the same held-out rows of the one-net SiD's self-play (stu_eval: the tricks its first card gives up
# against the rollouts' values), read as the bot it plays as. Nets go to models/cardplay/stu-exp-human-20261114/<tag>.npz
# for the bots stu<tag>-n (the net alone) and stu<tag>-pst (inside the one-net rollout bot); logs and scores to pub/exp-human/.
set -euo pipefail
W=$HOME/work/loop; PY=$W/venv/bin/python; T=training/rollout-loop-20261113; X=$W/exp-human; P=$W/pub/exp-human
FEED=${FEED:-feed/usbc-human-20261114}
BIG=${BIG:-$HOME/work/plan/rnet2w/data/train.npz}
R1=${R1:-$W/pub/train-r1/policy.npz}; R3=${R3:-$W/pub/train-r3/policy.npz}
THREADS=${THREADS:-8}
cd "$(dirname "$0")/../.."
OUT=models/cardplay/stu-exp-human-20261114
mkdir -p "$X" "$P" "$OUT"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$P/timeline.log"; }
export OPENBLAS_NUM_THREADS=$THREADS OMP_NUM_THREADS=$THREADS MKL_NUM_THREADS=$THREADS
rows() { "$PY" -c "import numpy as np, sys; print(len(np.load(sys.argv[1], mmap_mode='r')['deal']))" "$1"; }
keep() {   # tag net-file: the net where its bots read it, its scores and log for the publisher
  cp -f "$2" "$OUT/$1.npz"; mkdir -p "$P/$1"
  cp -f "$X/$1/metrics.json" "$X/$1.log" "$P/$1/" 2>/dev/null || true
  [ -f "$X/$1-score/metrics.json" ] && cp -f "$X/$1-score/metrics.json" "$P/$1/metrics_score.json"
  sha256sum "$OUT/$1.npz" | cut -c1-64 > "$P/$1/policy.sha256"
  say "net $1: sha256 $(cut -c1-16 "$P/$1/policy.sha256")"
}
tune() {   # tag set held-out-set starting-net init-as [--all-train]: a round's recipe, the last epoch kept
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$X/$2.npz" --val-data "$X/$3.npz" --out "$X/$1" --kind suit --width 768 \
    --epochs 4 --batch 256 --lr 1e-4 --id-dropout 0 --save-epochs --init "$4" ${5:+--init-as "$5"} ${6:-} --compare "$R3" \
    > "$X/$1.log" 2>&1 || { say "training $1 failed: $(tail -n 3 "$X/$1.log" | tr '\n' ' ' | cut -c1-300)"; exit 1; }
  keep "$1" "$X/$1/policy_epoch4.npz"
}
score() {   # tag set held-out-set width: the saved net on the held-out set, nothing trained (a rate of 1e-12)
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$X/$2.npz" --val-data "$X/$3.npz" --out "$X/$1-score" --kind suit --width "$4" \
    --epochs 1 --batch 512 --lr 1e-12 --id-dropout 0 --init "$X/$1/policy.npz" > "$X/$1-score.log" 2>&1 \
    || { say "scoring $1 failed: $(tail -n 3 "$X/$1-score.log" | tr '\n' ' ' | cut -c1-300)"; exit 1; }
}

for stage in "$@"; do
say "stage $stage; source $(git rev-parse --short HEAD); threads $THREADS"
case "$stage" in
sets)
  git fetch -q --depth 1 origin "$FEED"
  for s in human bot mixed stu_eval stu_eval_usbc; do
    git show "FETCH_HEAD:$s.npz" > "$X/$s.z"
    "$PY" -c "import numpy as np, sys; z = np.load(sys.argv[1]); np.savez(sys.argv[2], **{k: z[k] for k in z.files})" "$X/$s.z" "$X/$s.npz"
    rm -f "$X/$s.z"; say "set $s: $(rows "$X/$s.npz") rows"
  done ;;
e1)
  tune hf human stu_eval_usbc "$R3" usbc=stup0
  tune bf bot stu_eval "$R3" ''
  tune mf mixed stu_eval "$R3" usbc=stup0
  for trio in "hs human stu_eval_usbc" "bs bot stu_eval"; do
    read -r tag data held <<< "$trio"
    nice -n 10 "$PY" scripts/train_rollout_net.py --data "$X/$data.npz" --out "$X/$tag" --kind suit --width 256 --epochs 40 --patience 4 \
      --batch 256 --lr 2e-3 --save-epochs > "$X/$tag.log" 2>&1 || { say "training $tag failed: $(tail -n 3 "$X/$tag.log" | tr '\n' ' ' | cut -c1-300)"; exit 1; }
    score "$tag" "$data" "$held" 256
    keep "$tag" "$X/$tag/policy.npz"
  done ;;
mini)
  # About 10,000 pure-Stu boards: round 3's own training rows and the blocks of azure6 it fetched, whole deals at random.
  # shellcheck disable=SC2046
  nice -n 10 "$PY" $T/usbc/human_sets.py --merge "$X/stu_all.npz" "$W/r3/stu_train.npz" $(ls "$W"/in/rows-azure6/*.npz) | tee -a "$P/timeline.log"
  nice -n 10 "$PY" $T/sample_set.py "$X/stu_all.npz" "$X/stu10.npz" --rows 410000 --seed 2 | tee -a "$P/timeline.log"
  rm -f "$X/stu_all.npz"
  nice -n 10 "$PY" $T/sample_set.py "$BIG" "$X/replay10.npz" --rows "$(rows "$X/stu10.npz")" --seed 1 | tee -a "$P/timeline.log"
  nice -n 10 "$PY" $T/usbc/human_sets.py --merge "$X/m10.npz" "$X/stu10.npz" "$X/replay10.npz" | tee -a "$P/timeline.log"
  nice -n 10 "$PY" $T/usbc/human_sets.py --merge "$X/m10h.npz" "$X/stu10.npz" "$X/human.npz" "$X/replay10.npz" | tee -a "$P/timeline.log"
  nice -n 10 "$PY" $T/usbc/human_sets.py --merge "$X/m10h4.npz" "$X/stu10.npz" "$X/human.npz" "$X/human.npz" "$X/human.npz" "$X/human.npz" "$X/replay10.npz" | tee -a "$P/timeline.log"
  tune m10 m10 stu_eval "$R1" stup0=stu0 --all-train
  tune m10h m10h stu_eval "$R1" stup0=stu0,usbc=stu0 --all-train
  tune m10h4 m10h4 stu_eval "$R1" stup0=stu0,usbc=stu0 --all-train
  rm -f "$X/m10.npz" "$X/m10h.npz" "$X/m10h4.npz" ;;
scratch)
  nice -n 10 "$PY" $T/usbc/human_sets.py --merge "$X/s10h.npz" "$X/stu10.npz" "$X/human.npz" | tee -a "$P/timeline.log"
  cp -f "$X/stu10.npz" "$X/s10.npz"
  for tag in s10 s10h; do
    nice -n 10 "$PY" scripts/train_rollout_net.py --data "$X/$tag.npz" --all-train --val-data "$X/stu_eval.npz" --out "$X/$tag" --kind suit --width 512 \
      --epochs 6 --batch 512 --lr 2e-3 --save-epochs --compare "$R3" > "$X/$tag.log" 2>&1 || { say "training $tag failed: $(tail -n 3 "$X/$tag.log" | tr '\n' ' ' | cut -c1-300)"; exit 1; }
    keep "$tag" "$X/$tag/policy.npz"
  done
  rm -f "$X/s10.npz" "$X/s10h.npz" ;;
*) say "unknown stage $stage"; exit 1 ;;
esac
done

# Scores so far: each net on the held-out SiD rows (stu_eval), epoch by epoch, and round 3's net on the same rows.
"$PY" - "$X" <<'PY' | tee -a "$P/timeline.log"
import glob, json, os, sys
X = sys.argv[1]
print('%-6s %-9s | %s | %s' % ('net', 'rows', 'held-out SiD rows by epoch: log-loss / exact card / tricks its first card gives up', "round 3's net there"))
for d in sorted(glob.glob(f'{X}/*/metrics.json')):
    tag = os.path.basename(os.path.dirname(d))
    m = json.load(open(d))
    if tag.endswith('-score'):
        v = m['validation']['all']
        print('%-6s %-9s | scored on the SiD rows: %.4f / %.4f / %s' % (tag[:-6], '', v['nll'], v['agree'], v.get('regret')))
        continue
    hist = ' '.join('%d: %.4f/%.4f/%s' % (h['epoch'], h['val']['nll'], h['val']['agree'], h['val'].get('regret')) for h in m.get('history', []))
    cmp_ = ' '.join('%.4f/%.4f/%s' % (c['all']['nll'], c['all']['agree'], c['all'].get('regret')) for c in (m.get('compared') or {}).values())
    print('%-6s %-9d | %s (kept %s; held-out set %s) | %s' % (tag, m['train_examples'], hist, m['selected_epoch'], m.get('val_data') or 'its own deals', cmp_))
PY
say "done: $*"

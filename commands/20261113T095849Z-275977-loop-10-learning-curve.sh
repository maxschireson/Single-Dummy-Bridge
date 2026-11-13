# boxctl: timeout=3000
# boxctl: timeout=3000
# loop session (Max, 09:54 UTC: how much training data to make a meaningful impact on a net trained on many boards
# already?): measure it on the boards in hand. Stu's rows are built from the records so far; the 200 most recent boards
# are held out; rollout net v2 (Stu's vectors started from 8s-32's) is fine-tuned on an eighth, a quarter, a half and all
# of the rest, and each is scored on the held-out boards for how well it predicts Stu's card. Runs at Nice 10 with four
# threads beside the collection, from a second checkout; nothing of the collection's is touched.
set -euo pipefail
COMMIT=db83b7ae8c0419cefc252b4c7eb2cf2d8817bda9
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python; L=$W/lc
if [ ! -d "$S2/.git" ]; then cp -a "$W/src" "$S2"; fi
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q "$COMMIT"
git -C "$S2" log -1 --format='source %h %s' | cut -c1-110
cd "$S2"
rm -rf "$L"; mkdir -p "$L/train" "$L/held"
find "$W/runs/s0/episodes" -name '*.json.gz' -mmin +1 | sort > "$L/s0.txt"
n=$(wc -l < "$L/s0.txt"); echo "s0 records $n, r0 records $(ls "$W/runs/r0/episodes" | wc -l)"
head -n $((n - 200)) "$L/s0.txt" | xargs -I{} ln {} "$L/train/"
tail -n 200 "$L/s0.txt" | xargs -I{} ln {} "$L/held/"
for f in "$W"/runs/r0/episodes/*.json.gz; do ln "$f" "$L/train/r0-$(basename "$f")"; done
SC=models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz
AL=stu0a=stu0,stu0b=stu0,z0a-v2=stu0,z0b-v2=stu0
for part in train held; do
  nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes "$L/$part" --scorer "$SC" --out "$L/$part.npz" --workers 4 --policy-only --rollout-gap --alias "$AL" 2>&1 | tail -1
done
export OPENBLAS_NUM_THREADS=4 OMP_NUM_THREADS=4 MKL_NUM_THREADS=4 XLA_FLAGS="--xla_cpu_multi_thread_eigen=true intra_op_parallelism_threads=4"
V2=models/cardplay/rollout-net-v2-20261113/policy_epoch5.npz
run() {  # name fraction epochs lr
  nice -n 10 "$PY" scripts/train_rollout_net.py --data "$L/train.npz" --all-train --val-data "$L/held.npz" --out "$L/run-$1" --width 768 \
    --fraction "$2" --epochs "$3" --patience 2 --batch 256 --lr "$4" --id-dropout 0 --init "$V2" --init-as stu0=8s-32 \
    --compare "$V2" --compare models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --compare models/cardplay/rollout-net-v1-20261113/policy_ft.npz > "$L/run-$1.log" 2>&1 || { echo "run $1 failed"; tail -n 3 "$L/run-$1.log"; }
}
t0=$(date +%s)
run base 1.0 1 1e-12
run f8 0.125 12 3e-4
run f4 0.25 12 3e-4
run f2 0.5 12 3e-4
run f1 1.0 12 3e-4
echo "training: $(( $(date +%s) - t0 )) s"
"$PY" - <<'PY'
import json, os
import numpy as np
L = os.path.expanduser('~/work/loop/lc')
z = np.load(f'{L}/train.npz'); h = np.load(f'{L}/held.npz')
print('training set: deals', len(z['family']), 'rows', len(z['deal']), '| held out: deals', len(h['family']), 'rows', len(h['deal']), '| rows with the rollouts\' gap (some cards unrated):', int((h['gap'] < 0).any(axis=1).sum()))
def line(tag, m, deals):
    v = m['validation']; a, t7 = v['all'], v['from_trick_7']
    print(f"{tag:5} {deals:5} boards | all: nll {a['nll']:.4f} agree {a['agree']:.4f} | from trick 7: nll {t7['nll']:.4f} agree {t7['agree']:.4f} n {t7['n']} | rated_pick {a.get('rated_pick')} regret {a.get('regret')} | epoch {m.get('selected_epoch')}")
for tag in ('base', 'f8', 'f4', 'f2', 'f1'):
    p = f'{L}/run-{tag}/metrics.json'
    if not os.path.exists(p):
        print(tag, 'no metrics'); continue
    m = json.load(open(p))
    line(tag, m, 0 if tag == 'base' else m.get('train_deals'))
m = json.load(open(f'{L}/run-base/metrics.json'))
print('ids blanked (v2 as a generic player):', json.dumps(m['who_use']['blank']['all']))
for k, v in (m.get('compared') or {}).items():
    print('compared', os.path.basename(k), json.dumps({x: v[x] for x in ('all', 'from_trick_7') if x in v})[:300] if isinstance(v, dict) else str(v)[:200])
print('tie_nll (log of the count of equal-best rated cards), all held-out rows with a gap:', m['validation']['all'].get('tie_nll'), '| uniform_nll', m['validation']['all'].get('uniform_nll'))
PY
tail -n 1 "$W/runs/s0.log" | cut -c1-120; date -u +%FT%TZ

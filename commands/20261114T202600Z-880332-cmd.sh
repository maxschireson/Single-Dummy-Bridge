# boxctl: timeout=900
# loop session (Max, 20:18 UTC: clear ownership for the approved recommendations): read-only exports for the owners, written
# under ~/work/loop/pub so the publisher pushes them to transfer/rollout-loop-azure5-20261113:
#   train-r4c/val.npz          round 4's held-out rows, compressed (P01's acceptance: codex-stu-efficiency)
#   train-r4c/inputs.json      round 4c's inputs: record lists with sha256, the other row files with sha256, the arena sample,
#                              replay and trainer settings (P03's parity: codex-stu-efficiency)
#   samples/sp3s-200/          200 episode files of sp3s with their inside-rollout pairs (H02's extractor: codex-stu-harvest)
# Nice 19, one core, beside the width test. Nothing is moved or deleted.
set -uo pipefail
W=$HOME/work/loop; R=$W/r4c; P=$W/pub/train-r4c; PY=$W/venv/bin/python
ls "$R" | head -20 | tr '\n' ' '; echo
ls -la "$R/val.npz" 2>/dev/null | cut -c1-120
mkdir -p "$P" "$W/pub/samples/sp3s-200"
nice -n 19 "$PY" - "$R" "$P" "$W" <<'PY'
import hashlib, json, os, sys, glob, time, numpy as np
R, P, W = sys.argv[1:4]
z = np.load(R + '/val.npz', allow_pickle=True)
np.savez_compressed(P + '/val.npz', **{k: z[k] for k in z.files})
print('val.npz:', len(z['deal']), 'rows,', len(z['family']), 'deals; bots', [str(b) for b in z['bot_names']], '; compressed', os.path.getsize(P + '/val.npz') // 1024, 'KB')
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()
out = dict(round='r4c', note='inputs of round 4c (stu4c), trained 14:47-15:16 UTC on 14 Nov on azure5 by round4.sh -> round2.sh; files are on azure5 under ~/work/loop',
           trainer=dict(script='scripts/train_rollout_net.py', width=768, epochs=4, lr=1e-4, batch=256, id_dropout=0, patience=2, all_train=True,
                        init='pub/train-r1/policy.npz (transfer/rollout-loop-azure5-20261113:train-r1/policy.npz)',
                        init_as='stup0=stu0,9a-32=8s-32,8x3-32=8s-32', select='stup0', forget=0.02, save_epochs=True, val_data='val.npz (this folder)'),
           replay=dict(big='~/work/plan/rnet2w/data/train.npz (rollout net v2\'s set, 30.4M rows)', script='training/rollout-loop-20261113/sample_set.py', seed=1, rows=1591348, factor=0.3333),
           noreplay=[], parts={})
for part in ('train', 'held', 'test'):
    files = sorted(glob.glob(f'{R}/{part}/*.json.gz'))
    out['parts'][part] = [[os.path.basename(f), sha(f)] for f in files]
    print(part, len(files), 'records')
cut = time.mktime(time.strptime('2026-11-14 14:11:41', '%Y-%m-%d %H:%M:%S')) - time.timezone
extra = sorted([f for f in glob.glob(W + '/in/rows-*/*.npz') + glob.glob(W + '/in/cut-*/*.npz') if os.path.getmtime(f) <= cut])
arena = W + '/r4arena/arena.npz'
out['extra'] = [[os.path.relpath(f, W), sha(f), int(len(np.load(f, allow_pickle=True)['deal']))] for f in extra]
print('extra row files dated before the cut:', len(extra), '| arena rows file present:', os.path.exists(arena))
samp = sorted(glob.glob(W + '/r4arena/eps_sample/*.json.gz'))
out['arena'] = dict(sample=[[os.path.basename(f), sha(f)] for f in samp], rows_file='r4arena/arena.npz (removed after the round)' if not os.path.exists(arena) else 'r4arena/arena.npz',
                    builder='training/rollout-loop-20261113/round4_arena.sh SAMPLE=500,2100 (seed 5)')
print('arena sample records:', len(samp))
json.dump(out, open(P + '/inputs.json', 'w'), indent=0)
print('inputs.json', os.path.getsize(P + '/inputs.json') // 1024, 'KB')
PY
ls "$W/runs/sp3s/episodes" | head -n 200 | while read -r f; do cp -f "$W/runs/sp3s/episodes/$f" "$W/pub/samples/sp3s-200/"; done
cp -f "$W/runs/sp3s/manifest.json" "$W/pub/samples/sp3s-200/manifest.json"
echo "sample: $(ls "$W/pub/samples/sp3s-200" | wc -l) files, $(du -sh "$W/pub/samples/sp3s-200" | cut -f1)"
date -u +%T

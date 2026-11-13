# boxctl: timeout=600
# boxctl: timeout=600
# loop session: a quick check of gen7_build_dataset --rollout-layouts on 12 of azure6's records (second checkout, Nice 10).
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 5258edef45ba8021447b8ae22f1df306cfc7ea18
for d in bridge_harness/libbridge_dds.so models/cardplay; do [ -e "$S2/$d" ] && [ ! -L "$S2/$d" ] && rm -rf "$S2/$d"; ln -sfn "$W/src/$d" "$S2/$d"; done
cd "$S2"; mkdir -p /tmp/kt/eps; rm -f /tmp/kt/eps/*; ls "$W/runs/sp0c/episodes" | tail -n 12 | while read f; do ln -sf "$W/runs/sp0c/episodes/$f" /tmp/kt/eps/; done
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
nice -n 10 "$PY" scripts/gen7_build_dataset.py --episodes /tmp/kt/eps --scorer models/cardplay/hand-fit-scorer-v0-2026-11-11/hand_fit_v0.npz --out /tmp/kt/all.npz --workers 2 --policy-only --rollout-gap --rollout-layouts 8,16,32 --alias "$(cat training/rollout-loop-20261113/alias.txt)" 2>&1 | tail -n 1
nice -n 10 "$PY" - <<'PY'
import numpy as np
z = np.load('/tmp/kt/all.npz', allow_pickle=True)
g, m = z['gap'].astype(float), z['meta']
rolled = (m[:, 10] == 1)
print('rows', len(g), 'rated rows', int(rolled.sum()))
for k in (8, 16, 32):
    gk = z[f'gap_k{k}'].astype(float); ck = z[f'card_k{k}']
    both = rolled & (gk >= 0).any(1)
    diff = np.abs(np.where((g >= 0) & (gk >= 0), g - gk, 0)).sum(1)[both]
    print(f'k={k}: card changed {int((ck != m[:, 0]).sum())}, kept full {int(z[f"full_k{k}"].sum())}, mean |gap diff| a row {diff.mean():.3f}, rated cards same set {float(((g >= 0) == (gk >= 0))[both].all(1).mean()):.3f}')
PY

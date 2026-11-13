# boxctl: timeout=1500
# boxctl: timeout=1500
# sidnet: E1's declaring heads split by whether some card guarantees the target (experiments/sid_loop/e1_split.py).
set -euo pipefail
W=$HOME/work/sidnet; cd "$W/src"
git fetch -q --depth 1 origin research/sid-net-s0-20261113 && git reset -q --hard FETCH_HEAD
echo "source $(git rev-parse --short HEAD)"
OMP_NUM_THREADS=8 $HOME/work/venv/bin/python experiments/sid_loop/e1_split.py --data "$W/data/freshB.npz" --net "$W/s0/policy.npz" --out "$W/e1/split.json" | tee "$W/e1/split.txt" | cut -c1-330

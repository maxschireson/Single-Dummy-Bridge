# boxctl: timeout=900
# p41: base setup on the temporary training box. Python venv with numpy, jax and optax; the Gen 7 prototype
# source at fb617a6 (the commit v4 was trained from); v4, v3.1 and the hand-fit scorer restored from their parts.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive
sudo apt-get update -qq >/dev/null 2>&1 || true
sudo apt-get install -y -qq python3-venv python3-pip git >/dev/null 2>&1
mkdir -p ~/work/p41/{eps,data,runs,logs,git} && cd ~/work
python3 -m venv venv && . venv/bin/activate
pip install -q --upgrade pip
pip install -q numpy jax optax
git init -q repo && cd repo
git remote add origin https://github.com/maxschireson/Single-Dummy-Bridge
git fetch -q --depth=1 origin fb617a64f6ca037103b15f37ddda7bc9c949a86a && git checkout -q FETCH_HEAD
for m in gen7-policy-v4-2026-11-11 gen7-policy-v3.1-2026-11-11 hand-fit-scorer-v0-2026-11-11; do (cd models/cardplay/$m && python restore.py >/dev/null && ls -la *.npz | awk '{print $5, $9}'); done
python - <<'PY'
import jax, optax, numpy, os
print('jax', jax.__version__, 'optax', optax.__version__, 'numpy', numpy.__version__, 'cpus', os.cpu_count())
PY
nproc; free -g | sed -n 2p; df -h ~ | tail -1; lscpu | grep -E "Model name|Thread|Core|Socket" | sed 's/  */ /g'
git log -1 --format='source %h %s' | cut -c1-120

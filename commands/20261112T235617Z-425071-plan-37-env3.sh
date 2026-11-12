# boxctl: timeout=400
# boxctl: timeout=300
# plan session: what a training run on this box would have: python packages, disk, memory, the hand-fit scorer.
set -uo pipefail
P=$HOME/work/plan; PY=$HOME/work/venv/bin/python
$PY -c "import jax, optax, numpy; print('jax', jax.__version__, 'optax', optax.__version__, 'numpy', numpy.__version__)" 2>&1 | tail -1
PYTHONPATH=$P/pylib $PY -c "import jax, optax; print('pylib jax', jax.__version__)" 2>&1 | tail -1
df -h $HOME | tail -1; free -g | head -2; nproc; uptime
find $HOME/work -name "hand_fit_v0*.npz" 2>/dev/null | head -5
find $HOME/work -name "gen7_policy_v4.1.npz" 2>/dev/null | head -3
ls $HOME/work | head -30

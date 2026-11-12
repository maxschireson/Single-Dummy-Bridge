# boxctl: timeout=2400
# boxctl: timeout=2400
# g8: the arena runtime needs TensorFlow for the bidders (this box's environment was built without it). Install it,
# then run the preflight on the dry run prepared by the previous command. Nothing is launched.
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; D=$G/src-dry
"$HOME/work/venv/bin/pip" install -q "tensorflow-cpu==2.21.0" 2>&1 | tail -2
"$PY" -c "import tensorflow as tf; print('tensorflow', tf.__version__)" 2>&1 | tail -1
cd "$D" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 TF_NUM_INTRAOP_THREADS=1 TF_NUM_INTEROP_THREADS=1 BRIDGE_DDS_CACHE=
rm -rf "$G/runs/arena-dry-smoke"
echo "== preflight"
nice -n 5 "$PY" ops/smoke_gen7.py --run "$G/runs/arena-dry" --out "$G/runs/arena-dry-smoke" --deals 2 2>&1 | grep -v "^WARNING\|tensorflow/\|oneDNN\|cpu_feature" | tail -16 | cut -c1-400
ls "$G/runs/arena-dry-smoke" 2>/dev/null | head -8 | tr '\n' ' '; echo

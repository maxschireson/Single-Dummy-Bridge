# boxctl: timeout=1000
# boxctl: timeout=900
# plan session: h5py for my matches on azure5, installed beside my own files (~/work/plan/pylib), not into the shared venv.
set -uo pipefail
P=$HOME/work/plan; PY=$HOME/work/venv/bin/python
"$PY" -m pip install -q --target "$P/pylib" h5py 2>&1 | tail -2
PYTHONPATH="$P/pylib" "$PY" -c "import h5py, numpy; print('h5py', h5py.__version__, 'numpy', numpy.__version__, numpy.__file__)" 2>&1 | tail -1
cd "$P/src" && git fetch -q --depth 1 origin 2a3a4111f4e28c9d838ad8e658c6e0b9c7854633 2>/dev/null; git log -1 --format='queue source now %h' 

# loop session: read plan's queue files (read-only) to pause the queue without losing its running job
cd ~/work/plan
echo "== queue.sh"; cat queue.sh
echo "== queue.pos"; cat queue.pos; echo
echo "== queue.txt (numbered)"; cat -n queue.txt | cut -c1-330
echo "== queue.log (tail)"; tail -n 12 queue.log | cut -c1-330
echo "== pub.sh"; cat pub.sh
echo "== unit"; systemctl cat plan-queue.service 2>/dev/null | head -30
echo "== venv"; ~/work/venv/bin/python -V; ~/work/venv/bin/python -c "import numpy, jax, optax, h5py; print(numpy.__version__, jax.__version__, optax.__version__, h5py.__version__)" 2>&1 | tail -1
ls ~/work/plan/bin ~/work/plan/nets ~/work/plan/models 2>/dev/null | head -40
ls ~/work/plan/capsule | head; ls ~/work/plan/runs | head -20

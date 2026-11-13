# boxctl: timeout=900
# boxctl: timeout=900
# sidnet: update the source to the pushed tip (the running label stage keeps the files it has open), install JAX for
# the training stage, and queue the rest of the chain as unit sidnet-run2: it waits for sidnet-run to end, then runs
# build, buildB, train, e1 and push. Each stage refuses to start unless the stage before it finished.
set -euo pipefail
W=$HOME/work/sidnet; cd "$W/src"
git fetch -q --depth 1 origin research/sid-net-s0-20261113 && git reset -q --hard FETCH_HEAD
echo "source $(git rev-parse --short HEAD) $(git log -1 --format=%s | cut -c1-70)"
if ! PYTHONPATH=$W/pylib $HOME/work/venv/bin/python -c "import jax, optax" 2>/dev/null; then
  nice -n 19 $HOME/work/venv/bin/python -m pip install -q --target "$W/pylib" "jax[cpu]" optax > "$W/logs/pip.log" 2>&1
fi
PYTHONPATH=$W/pylib $HOME/work/venv/bin/python -c "import jax, optax; print('jax', jax.__version__, 'optax', optax.__version__)"
if systemctl is-active --quiet sidnet-run2; then echo "sidnet-run2 is already queued"; else
  sudo systemd-run --unit=sidnet-run2 --uid="$USER" --working-directory="$W/src" --setenv=HOME="$HOME" --property=Nice=10 \
    --setenv=STAGES="build buildB train e1 push" -- bash -c 'while systemctl is-active --quiet sidnet-run; do sleep 20; done; exec bash training/sid-net-s0-20261113/chain.sh'
fi
systemctl is-active sidnet-run sidnet-run2 | tr "\n" " "; echo
tail -1 "$W/logs/label.log" | cut -c1-200; ls "$W/labels" | wc -l; uptime | sed "s/.*load/load/"

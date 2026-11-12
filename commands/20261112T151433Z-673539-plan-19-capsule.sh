# boxctl: timeout=1000
# boxctl: timeout=900
# plan session: the match capsule (manifest, artifacts, assets; no episodes) under ~/work/plan/capsule on azure5, read from
# the capture feed branch. Touches nothing outside ~/work/plan.
set -uo pipefail
P=$HOME/work/plan; C=$P/capsule; G=$P/capsule.git; PY=$HOME/work/venv/bin/python
mkdir -p "$C"
if [ ! -d "$G" ]; then
  git init -q --bare "$G"; git -C "$G" remote add origin https://github.com/maxschireson/Single-Dummy-Bridge
  git -C "$G" config remote.origin.promisor true; git -C "$G" config remote.origin.partialclonefilter blob:none
fi
git -C "$G" fetch -q --depth 1 --filter=blob:none origin arena-gen6-gen7-capture-feed || { echo "fetch failed"; exit 1; }
git -C "$G" archive FETCH_HEAD recovery/manifest.json recovery/artifacts recovery/assets | tar -x -C "$C" || { echo "archive failed"; exit 1; }
du -sh "$C/recovery" | sed 's/^/capsule: /'; ls "$C/recovery" | tr '\n' ' '; echo
"$PY" -c "import h5py; print('h5py', h5py.__version__)" 2>&1 | tail -1
cd "$P/src" && git log -1 --format='source %h %s' | cut -c1-100
ls configs/plan-bots.json scripts/plan_match.py scripts/gen8_match.py 2>&1 | tr '\n' ' '; echo

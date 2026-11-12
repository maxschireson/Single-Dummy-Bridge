# boxctl: timeout=1500
# boxctl: timeout=1500
# g8: the nets alone against each other (no search at any trick), 1,000 boards each on two cores beside the running
# match. This sizes the leverage experiment: how much stronger v4 is than v0 and v2 as a player by itself.
set -uo pipefail
G=$HOME/work/g8; PY=$HOME/work/venv/bin/python; CAP=$HOME/work/capsule-gen7-capture/recovery
cd "$G/src" || exit 1
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 BRIDGE_DDS_CACHE=
for pair in n-v4~n-v0 n-v4~n-v2; do
  name=c0-$(echo "$pair" | sed 's/~n-/-v-/')
  nice -n 5 "$PY" -u scripts/gen8_match.py --source "$CAP" --bots configs/gen8-proto-bots.json --pair "$pair" --first 0 --deals 1000 --seed 83 \
    --workers 2 --out "$G/runs/$name" > "$G/runs/$name.log" 2>&1
  tail -1 "$G/runs/$name.log" | cut -c1-330
done

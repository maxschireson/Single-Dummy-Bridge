# boxctl: timeout=900
# boxctl: timeout=900
# loop session: a short throwaway test of gen8_match --recycle (fresh worker processes every 2 boards a worker) beside the
# collection: pure Stu's self-play, 2 workers at Nice 10, 8 training deals far from the collection's, into /tmp; from the
# second checkout (the collection's source is untouched). Then the memory now.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 474ed8bbfaa089d4eb9e08b4cb560bddffa58c01
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE= BRIDGE_NET_BF16=1
rm -rf /tmp/rtest
timeout 600 nice -n 10 "$PY" scripts/x8_match.py --source "$W/capsule/recovery" --bots configs/loop-bots.json --pair stu0-pa~stu0-pb --deals 8 --first 910000   --seed 9001 --workers 2 --out /tmp/rtest --episodes --one-room --recycle 2 2>&1 | grep -v Warning | tail -6
echo "results: $(wc -l < /tmp/rtest/results.jsonl), episodes: $(ls /tmp/rtest/episodes | wc -l)"
free -m | sed -n 2p; date -u +%FT%TZ

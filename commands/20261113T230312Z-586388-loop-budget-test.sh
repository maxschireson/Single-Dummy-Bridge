# boxctl: timeout=900
# boxctl: timeout=900
# loop session: a quick check of bench/budget.py (6 decisions of sp0d, reference 256 layouts, 2 workers at Nice 10,
# second checkout) beside the collection.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc; PY=$W/venv/bin/python
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 9c3467bfbf703b79b6cc3fa8c856f0c9136d24f9
cd "$S2"; export SURE_BIN=$W/bin/sure_cpp OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 BRIDGE_DDS_CACHE= BRIDGE_NET_BF16=1
mkdir -p /tmp/bt && rm -f /tmp/bt/* && ls "$W/runs/sp0d/episodes" | sed -n 1,6p | while read f; do ln -sf "$W/runs/sp0d/episodes/$f" /tmp/bt/; done
timeout 800 nice -n 10 "$PY" training/rollout-loop-20261113/bench/budget.py /tmp/bt --decisions 6 --workers 2 --reference 256 --out /tmp/bt/rows.jsonl 2>&1 | grep -v Warning | tail -14
head -c 600 /tmp/bt/rows.jsonl; echo; date -u +%FT%TZ

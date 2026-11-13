# boxctl: timeout=300
# boxctl: timeout=300
# loop session (Max, 22:31 UTC: "do a sweep to see how much more rollouts help"): bench/budget.py on 1,000 of sp0d's
# rollout decisions (one a table), every budget against a 1,024-layout reference of every card; a unit of its own beside
# the collection, 4 workers at Nice 10, from the second checkout. Results to pub/exp/ (the publisher pushes them).
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 15335540220f55f538aa770faebb01a8e3530ec4
mkdir -p "$W/pub/exp" /tmp/bsweep && rm -f /tmp/bsweep/* "$W/pub/exp/budget.jsonl"
ls "$W/runs/sp0d/episodes" | sort | awk 'NR % 3 == 0' | sed -n 1,1000p | while read f; do ln -sf "$W/runs/sp0d/episodes/$f" /tmp/bsweep/; done
echo "$(ls /tmp/bsweep | wc -l) records"
sudo systemctl reset-failed loop-budget 2>/dev/null || true
sudo systemd-run --unit=loop-budget --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" --setenv=SURE_BIN=$W/bin/sure_cpp \
  --setenv=OPENBLAS_NUM_THREADS=1 --setenv=OMP_NUM_THREADS=1 --setenv=MKL_NUM_THREADS=1 --setenv=BRIDGE_DDS_CACHE= --setenv=BRIDGE_NET_BF16=1 \
  --property=Nice=10 -- bash -c "$W/venv/bin/python training/rollout-loop-20261113/bench/budget.py /tmp/bsweep --decisions 1000 --workers 4 --reference 1024 --out $W/pub/exp/budget.jsonl 2>&1 | grep -v Warning > $W/pub/exp/budget.txt"
sleep 20; systemctl is-active loop-budget loop-collect | tr '\n' ' '; cat "$W/pub/exp/budget.txt" | head -3; date -u +%FT%TZ

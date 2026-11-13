# boxctl: timeout=3000
# boxctl: timeout=3000
# loop session: round 1's net, quick variant (PLAN.md on the loop's branch). From the second checkout, so the collection's
# tree is not touched; Nice 10, four threads, beside the collection. Reads the plan session's warm-run set and held-out
# set (read-only) for the rows of the bots the net already knows.
set -euo pipefail
COMMIT=aa1c2f86efcdd94ac425f01556f63f6e6bd9076f
W=$HOME/work/loop; S2=$W/src-lc
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q "$COMMIT"
git -C "$S2" log -1 --format='source %h %s' | cut -c1-110
rm -rf "$W/lc"
t0=$(date +%s)
bash "$S2/training/rollout-loop-20261113/round1.sh" r1 250 4 3e-4 2>&1 | cut -c1-260 | tail -32
echo "round1.sh: $(( $(date +%s) - t0 )) s"; ls -la "$W/pub/train-r1" | tail -8; tail -n 1 "$W/runs/s0.log" | cut -c1-110; date -u +%FT%TZ

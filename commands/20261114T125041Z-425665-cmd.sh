# boxctl: timeout=14400
# loop session: round 4 on azure5 (all 8 cores; the human-boards experiment's units stop here), in two nets (Max, 09:39 UTC):
# the other boxes' blocks and cut files (fetch_rows.sh CUT=1, once each box's cut line is on its branch); the arena's rows
# (round4_arena.sh, selected at 06:48); round2.sh r4 on azure5's own runs, from round 1's net, 4 epochs at 1e-4, the epoch
# best on pure Stu's held-out cards with the other bots' log-loss within 0.02 of the start, WITH every human table of the
# USBCs of 2021 to 2023 (they draw no replay rows); then round2.sh r4c, the control, the same without them. Indicator 1 on
# the test set for each against round 3's net and against each other; then rungs.sh jobs-azure5-r4.txt (the two nets alone
# against each other and round 3's, then inside the one-net bot), which restarts the collection.
set -euo pipefail
COMMIT=2dde3490d3e4a9518e4be550d784c951ad1a235f
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python; X=$W/exp-human
sudo systemctl stop loop-human loop-human2 loop-human3 loop-human4 loop-collect loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true; pkill -u "$USER" -f scripts/train_rollout_net.py 2>/dev/null || true; sleep 3
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'; cd "$S"
collect() {
  sudo systemctl reset-failed loop-collect 2>/dev/null || true
  sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure5.txt"
}
echo "$(date -u +%FT%TZ) round 4's cut: the human-boards experiment's matches stop where they are; azure5 trains round 4's two nets" >> "$W/runs.log"
rm -f "$W/r3/train.npz" "$W/r3/replay.npz" "$X"/stu10.npz "$X"/replay10.npz "$X"/s10.npz "$X"/m10*.npz "$X"/hA.npz "$X"/bA.npz "$X"/sAh.npz "$X"/stu_all.npz "$X"/human_unfit_blank.npz
df -h --output=avail "$HOME" | tail -1
for i in $(seq 1 40); do                     # each box's cut line reaches its branch with its publisher
  missing=""
  for box in azure3 azure6 azure2 azure1; do D=$W/in/git-$box; [ -d "$D/.git" ] || git init -q "$D"
    git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge "transfer/rollout-loop-$box-20261113"
    git -C "$D" show FETCH_HEAD:rows-cut/cut.log 2>/dev/null | grep -q "cut round4 done" || missing="$missing $box"
  done
  [ -z "$missing" ] && break; [ "$i" = 40 ] && echo "going on without the cut of:$missing"; sleep 60
done
CUT=1 bash $T/fetch_rows.sh azure3 azure6 azure2 azure1
while systemctl is-active -q loop-arena; do sleep 20; done      # the arena's rows, begun at 12:17 in a unit of their own
[ -s "$W/r4arena/arena.npz" ] || WORKERS=8 bash $T/round4_arena.sh "$W/r4arena" 45000 > "$W/r4arena.out" 2>&1 || { echo "arena rows failed"; tail -n 5 "$W/r4arena.out"; collect; exit 1; }
tail -n 4 "$W/r4arena/arena.log" | cut -c1-220
EXTRA="$(ls "$W"/in/rows-azure*/*.npz "$W"/in/cut-azure*/*.npz 2>/dev/null | tr '\n' ' ') $W/r4arena/arena.npz"
HUMAN="$X/human_fit.npz $X/human_unfit.npz"
RUNS=spr0,sp0,sps0,sp3s,sg8t1
for r in ${RUNS//,/ }; do echo -n "$r $(wc -l < "$W/runs/$r/results.jsonl") tables; "; done; echo "$(echo $EXTRA | wc -w) row files from the other boxes and the arena"
THREADS=8 SELECT=stup0 FORGET=0.02 TEST=300 EXTRA="$EXTRA" NOREPLAY="$HUMAN" INIT_AS=9a-32=8s-32,8x3-32=8s-32,usbc=stu0 bash $T/round2.sh r4 $RUNS 300 4 1e-4 > "$W/r4.out" 2>&1 \
  || { echo "round2.sh r4 failed"; tail -n 15 "$W/r4.out"; collect; exit 1; }
cut -c1-235 "$W/r4/timeline.log"
mkdir -p "$S/models/cardplay/stu-net-r4-20261113"; cp -f "$W/r4/net/policy.npz" "$S/models/cardplay/stu-net-r4-20261113/policy.npz"
echo "r4 sha256 $(sha256sum "$S/models/cardplay/stu-net-r4-20261113/policy.npz" | cut -c1-64) at $(date -u +%FT%TZ)"
rm -f "$W/r4/train.npz" "$W/r4/replay.npz"
THREADS=8 SELECT=stup0 FORGET=0.02 TEST=300 EXTRA="$EXTRA" INIT_AS=9a-32=8s-32,8x3-32=8s-32 bash $T/round2.sh r4c $RUNS 300 4 1e-4 > "$W/r4c.out" 2>&1 \
  || { echo "round2.sh r4c failed"; tail -n 15 "$W/r4c.out"; collect; exit 1; }
cut -c1-235 "$W/r4c/timeline.log"
mkdir -p "$S/models/cardplay/stu-net-r4c-20261113"; cp -f "$W/r4c/net/policy.npz" "$S/models/cardplay/stu-net-r4c-20261113/policy.npz"
echo "r4c sha256 $(sha256sum "$S/models/cardplay/stu-net-r4c-20261113/policy.npz" | cut -c1-64) at $(date -u +%FT%TZ)"
rm -f "$W/r4c/train.npz" "$W/r4c/replay.npz"
export OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8
R3=$S/models/cardplay/stu-net-r3-20261113/policy.npz
echo "== indicator 1 on the test set: round 3's net -> r4 (with the human tables)"; "$PY" $T/regret_pairs.py "$W/r4c/stu_test.npz" "$R3" "$W/r4/net/policy.npz" --json "$W/pub/train-r4/test-policy-r3.json" || true
echo "== test set: round 3's net -> r4c (control)"; "$PY" $T/regret_pairs.py "$W/r4c/stu_test.npz" "$R3" "$W/r4c/net/policy.npz" --json "$W/pub/train-r4c/test-policy-r3.json" || true
echo "== test set: r4c -> r4"; "$PY" $T/regret_pairs.py "$W/r4c/stu_test.npz" "$W/r4c/net/policy.npz" "$W/r4/net/policy.npz" --json "$W/pub/train-r4/test-policy-r4c.json" || true
echo "== the one-net SiD's held-out rows (the experiment's): r4c -> r4"; "$PY" $T/regret_pairs.py "$X/stu_eval.npz" "$W/r4c/net/policy.npz" "$W/r4/net/policy.npz" || true
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure5-r4.txt azure5
sleep 15; systemctl is-active loop-rungs loop-collect loop-publish | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ

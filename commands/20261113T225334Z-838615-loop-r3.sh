# boxctl: timeout=14400
# boxctl: timeout=14400
# loop session: round 3 on azure5, its collection paused for the training and the two net-alone rungs (all 8 cores):
# workers recycled from here on (~/work/loop/RECYCLE 20); the other boxes'
# blocks and cut files (fetch_rows.sh CUT=1); round2.sh r3 on spr0 then sp0 (the 300 newest of spr0 held out), from
# round 1's net, 4 epochs at 1e-4, the epoch best on pure Stu's held-out cards with the other bots' log-loss within 0.02
# of the start; indicator 1 with paired standard errors on a test set used for no choice (the 300 newest sp0 tables)
# against the start, round 2's net and the interim net; then
# rungs.sh jobs-azure5-r3.txt (round 3's net alone on gate deals 0-999, v2 alone on 200-499), which restarts the chains.
set -euo pipefail
COMMIT=1a40de0ca034c886228480e0d834550c7a2d19d2
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'; cd "$S"
echo 20 > "$W/RECYCLE"
collect() {
  sudo systemctl reset-failed loop-collect loop-collect-b 2>/dev/null || true
  sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure5.txt"
  sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure5b.txt"
}
sudo systemctl stop loop-collect loop-collect-b
echo "$(date -u +%FT%TZ) round 3's cut: sp0 and spr0 stopped; the collection is paused for round 3's training, then sps0 (pure rollout)" >> "$W/runs.log"
want="azure3:sp0b,spr0b azure6:sp0c,spr0c azure2:sp0d,spr0d azure1:sp0e,spr0e"
since=1794610294     # this round's cut began at 22:51Z
for i in $(seq 1 30); do                     # this round's cut files (written after it began) reach the branches with each box's publisher
  missing=""
  for b in $want; do box=${b%%:*}; D=$W/in/git-$box; [ -d "$D/.git" ] || git init -q "$D"
    git -C "$D" fetch -q --depth 1 https://github.com/maxschireson/Single-Dummy-Bridge "transfer/rollout-loop-$box-20261113"
    for r in $(echo "${b#*:}" | tr ',' ' '); do
      when=$(git -C "$D" show FETCH_HEAD:rows-cut/cut.log 2>/dev/null | grep " cut $r " | grep -v failed | tail -n 1 | cut -c1-20)
      t=$( [ -n "$when" ] && date -u -d "$when" +%s || echo 0)
      [ "$t" -ge "$since" ] || missing="$missing $box:$r"
    done
  done
  [ -z "$missing" ] && break; [ "$i" = 30 ] && echo "going on without fresh cut files for:$missing"; sleep 60
done
CUT=1 bash $T/fetch_rows.sh azure3 azure6 azure2 azure1
EXTRA=$(ls "$W"/in/rows-azure*/*.npz "$W"/in/cut-azure*/*.npz 2>/dev/null | tr '\n' ' ')
echo "spr0 $(wc -l < "$W/runs/spr0/results.jsonl") tables, sp0 $(wc -l < "$W/runs/sp0/results.jsonl"); $(echo $EXTRA | wc -w) row files from the other boxes"
THREADS=8 SELECT=stup0 FORGET=0.02 TEST=300 EXTRA="$EXTRA" bash $T/round2.sh r3 spr0,sp0 300 4 1e-4 > "$W/r3.out" 2>&1 || { echo "round2.sh failed"; tail -n 15 "$W/r3.out"; collect; exit 1; }
cut -c1-235 "$W/r3/timeline.log"
mkdir -p "$S/models/cardplay/stu-net-r3-20261113"; cp -f "$W/r3/net/policy.npz" "$S/models/cardplay/stu-net-r3-20261113/policy.npz"
export OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8
for head in policy value; do
  echo "== indicator 1 on the test set ($head head): start -> r3"; "$PY" $T/regret_pairs.py "$W/r3/stu_test.npz" "$W/r3/before/policy.npz" "$W/r3/net/policy.npz" --head $head --json "$W/pub/train-r3/test-$head-start.json" || true
  echo "== test set ($head head): round 2's net -> r3"; "$PY" $T/regret_pairs.py "$W/r3/stu_test.npz" "$S/models/cardplay/stu-net-r2-20261113/policy.npz" "$W/r3/net/policy.npz" --head $head --json "$W/pub/train-r3/test-$head-r2.json" || true
  echo "== test set ($head head): interim net (r3a) -> r3"; "$PY" $T/regret_pairs.py "$W/r3/stu_test.npz" "$S/models/cardplay/stu-net-r3a-20261113/policy.npz" "$W/r3/net/policy.npz" --head $head --json "$W/pub/train-r3/test-$head-r3a.json" || true
done
echo "== the validation set (it chose the epoch): start -> r3"; "$PY" $T/regret_pairs.py "$W/r3/val.npz" "$W/r3/before/policy.npz" "$W/r3/net/policy.npz" || true
sha256sum "$S/models/cardplay/stu-net-r3-20261113/policy.npz" | cut -c1-64
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure5-r3.txt azure5
sleep 15; systemctl is-active loop-rungs loop-collect loop-collect-b loop-publish | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ

#!/usr/bin/env bash
# Round 4 on the training box (azure5), in two nets (Max, 09:39 UTC on 14 November: "If we aren't sure we can do a R4a and
# an R4b"), run as a unit of its own so that the box's command queue stays free:
#   sudo systemd-run --unit=loop-r4 --uid=$USER --setenv=HOME=$HOME -- bash training/rollout-loop-20261113/round4.sh
# The other boxes' blocks and cut files are already fetched (fetch_rows.sh CUT=1) and the arena's records selected
# (round4_arena.sh). What it does:
# 1. The arena's rows from a sample of the selected records (ARENA: 500 of the BEN feed, 2,100 of the others; about 1.5
#    million rows). Every record would be about 14 million rows, four times the loop's own: the first try at this cut
#    (12:50 UTC) was sized by boards and could not have fitted azure5's disk.
# 2. round2.sh r4: from round 1's net, 4 epochs at 1e-4, the epoch best on pure Stu's held-out cards with the other bots'
#    log-loss within 0.02 of the start, on the loop's rows (about 3.1 million), the arena sample and a third as many
#    replay rows of rollout net v2's set (REPLAY 0.3333: arena and replay together come to about the loop's rows, the
#    share other bots' rows had in round 3), WITH every human table of the USBCs of 2021 to 2023 (they draw no replay).
# 3. round2.sh r4c: the control, the same without the human tables.
# 4. Indicator 1 on the test set for each against round 3's net and against each other; the nets where their bots read
#    them; then rungs.sh jobs-azure5-r4.txt (the nets alone, then inside the one-net bot), which restarts the collection.
# A net's big files (train.npz, replay.npz) are removed when it is trained or has failed; nothing starts with less than
# MIN_FREE_GB of disk free. The log is ~/work/loop/r4go.log.
set -uo pipefail
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113; PY=$W/venv/bin/python; X=$W/exp-human
ARENA=${ARENA:-500,2100}; REPLAY=${REPLAY:-0.3333}; RUNS=${RUNS:-spr0,sp0,sps0,sp3s,sg8t1}; MIN_FREE_GB=${MIN_FREE_GB:-14}
cd "$S"
say() { echo "$(date -u +%FT%TZ) $*" | tee -a "$W/r4go.log"; }
free_gb() { df --output=avail -BG "$HOME" | tail -n 1 | tr -dc 0-9; }
collect() {
  sudo systemctl reset-failed loop-collect 2>/dev/null || true
  sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$S/$T/chain.sh" "$S/$T/jobs-azure5.txt"
}
fail() { say "FAILED: $*"; rm -f "$W"/r4/train.npz "$W"/r4/replay.npz "$W"/r4c/train.npz "$W"/r4c/replay.npz; collect; exit 1; }
say "round 4 begins; source $(git rev-parse --short HEAD); arena sample $ARENA; replay x$REPLAY; disk free $(free_gb) GB"
sudo systemctl stop loop-collect loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f scripts/x8_match.py 2>/dev/null || true
rm -rf "$W/r4" "$W/r4c" "$W/r4arena/arena.npz"
[ "$(free_gb)" -ge "$MIN_FREE_GB" ] || fail "only $(free_gb) GB of disk free"
SKIP_SELECT=1 SAMPLE=$ARENA WORKERS=8 bash $T/round4_arena.sh "$W/r4arena" 45000 > "$W/r4arena.out" 2>&1 || fail "the arena's rows: $(tail -n 3 "$W/r4arena.out" | tr '\n' ' ' | cut -c1-300)"
tail -n 4 "$W/r4arena/arena.log" | cut -c1-260 | tee -a "$W/r4go.log"
EXTRA="$(ls "$W"/in/rows-azure*/*.npz "$W"/in/cut-azure*/*.npz 2>/dev/null | tr '\n' ' ') $W/r4arena/arena.npz"
HUMAN="$X/human_fit.npz $X/human_unfit.npz"
for f in $HUMAN; do [ -s "$f" ] || fail "no $f"; done
say "$(for r in ${RUNS//,/ }; do echo -n "$r $(wc -l < "$W/runs/$r/results.jsonl") tables; "; done)$(echo $EXTRA | wc -w) row files from the other boxes and the arena"
round() {   # name, the human tables or nothing
  local name=$1 human=$2
  [ "$(free_gb)" -ge "$MIN_FREE_GB" ] || fail "only $(free_gb) GB of disk free before $name"
  THREADS=8 SELECT=stup0 FORGET=0.02 TEST=300 EXTRA="$EXTRA" NOREPLAY="$human" REPLAY=$REPLAY \
    INIT_AS="9a-32=8s-32,8x3-32=8s-32${human:+,usbc=stu0}" bash $T/round2.sh "$name" "$RUNS" 300 4 1e-4 > "$W/$name.out" 2>&1 \
    || fail "round2.sh $name: $(tail -n 6 "$W/$name.out" | tr '\n' ' ' | cut -c1-500)"
  cut -c1-235 "$W/$name/timeline.log" >> "$W/r4go.log"
  mkdir -p "$S/models/cardplay/stu-net-$name-20261113"; cp -f "$W/$name/net/policy.npz" "$S/models/cardplay/stu-net-$name-20261113/policy.npz"
  rm -f "$W/$name/train.npz" "$W/$name/replay.npz"
  say "$name sha256 $(sha256sum "$S/models/cardplay/stu-net-$name-20261113/policy.npz" | cut -c1-64); disk free $(free_gb) GB"
}
round r4 "$HUMAN"
round r4c ""
export OPENBLAS_NUM_THREADS=8 OMP_NUM_THREADS=8
R3=$S/models/cardplay/stu-net-r3-20261113/policy.npz
{
  echo "== indicator 1 on the test set: round 3's net -> r4 (with the human tables)"; "$PY" $T/regret_pairs.py "$W/r4c/stu_test.npz" "$R3" "$W/r4/net/policy.npz" --json "$W/pub/train-r4/test-policy-r3.json"
  echo "== test set: round 3's net -> r4c (the control)"; "$PY" $T/regret_pairs.py "$W/r4c/stu_test.npz" "$R3" "$W/r4c/net/policy.npz" --json "$W/pub/train-r4c/test-policy-r3.json"
  echo "== test set: r4c -> r4"; "$PY" $T/regret_pairs.py "$W/r4c/stu_test.npz" "$W/r4c/net/policy.npz" "$W/r4/net/policy.npz" --json "$W/pub/train-r4/test-policy-r4c.json"
  echo "== the one-net SiD's held-out rows (the human-boards experiment's): r4c -> r4"; "$PY" $T/regret_pairs.py "$X/stu_eval.npz" "$W/r4c/net/policy.npz" "$W/r4/net/policy.npz"
} >> "$W/r4go.log" 2>&1 || true
cp -f "$W/r4go.log" "$W/pub/train-r4/r4go.log" 2>/dev/null || true
say "round 4's nets are trained; the nets-alone matches and the collection follow (rungs.sh jobs-azure5-r4.txt)"
bash "$S/$T/rungs.sh" jobs-azure5-r4.txt azure5

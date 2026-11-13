# boxctl: timeout=300
# boxctl: timeout=300
# loop session: a first run of round 2's training on azure5 beside the collection (4 threads at Nice 10), on the tables
# so far: pure Stu's rows, named stup0, from round 1's net with as many replay rows. The checkout only adds files and
# changes the trainer (the chain's scripts and job file are untouched), so the collection is not stopped.
set -euo pipefail
COMMIT=961bcf850d7492bc8933312127b85b2db1768546
W=$HOME/work/loop; S=$W/src
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113
git -C "$S" diff --stat HEAD "$COMMIT" | tail -6
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h %s' | cut -c1-100
echo "spr0 $(wc -l < "$W/runs/spr0/results.jsonl") tables, sp0 $(wc -l < "$W/runs/sp0/results.jsonl")"; ls -la "$W/pub/train-r1/policy.npz" | cut -c1-120
sudo systemctl stop loop-train2 2>/dev/null || true; sudo systemctl reset-failed loop-train2 2>/dev/null || true
sudo systemd-run --unit=loop-train2 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --setenv=THREADS=4 -- bash training/rollout-loop-20261113/round2.sh r2a spr0,sp0 150 4 1e-4
sleep 45; systemctl is-active loop-collect loop-publish loop-train2 | tr '\n' ' '; echo; cat "$W/r2a/timeline.log" 2>/dev/null | cut -c1-200; tail -n 1 "$W/runs.log" | cut -c1-140; free -g | sed -n 2p; date -u +%FT%TZ

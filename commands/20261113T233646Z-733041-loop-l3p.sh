# boxctl: timeout=300
# boxctl: timeout=300
# loop session: round 3's rung in the rollouts on azure1 (indicator 3): round 3's net put where its bots read it
# (get_net.sh, sha256 checked), then rungs.sh jobs-azure1-r3.txt in a unit of its own: the collection pauses for l3-p
# (pure Stu with round 3's net against Gen 8 card play, gate deals 500-999) and restarts after it.
set -euo pipefail
COMMIT=52033bcfd64000a61543b7d6839303360bd763e0
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
cd "$S"; bash $T/get_net.sh 3 a8cf8a94ebcf29da88c12d1fb26ad4b53a6322b5518905d41d961f04027428c9
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure1-r3.txt azure1
sleep 20; systemctl is-active loop-rungs loop-collect loop-collect-b loop-rows | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; date -u +%FT%TZ

# boxctl: timeout=300
# boxctl: timeout=300
# loop session: the BEN (200) baselines (Max, 01:43 UTC: "Ok switch!"), in a unit of its own
# (ben_session.sh jobs-azure3-ben4.txt): the collection pauses, BEN (200) servers start, b0-ps200 and b3-ps200
# bb-200v64 and bg-200 play, the BEN (200) servers stop and the collection restarts.
set -euo pipefail
COMMIT=228770dbd6a38c3bd3c28cf7472e74f41966243e
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
cd "$S"; bash $T/get_net.sh 3 a8cf8a94ebcf29da88c12d1fb26ad4b53a6322b5518905d41d961f04027428c9
for n in 1 2 3 4 5 6 7 8; do printf '%s ' "$(systemctl is-active ben-server@$n)"; done; echo
sudo systemctl reset-failed loop-bensession 2>/dev/null || true
sudo systemd-run --unit=loop-bensession --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/ben_session.sh" jobs-azure3-ben4.txt
sleep 45; systemctl is-active loop-bensession loop-chain loop-collect-b | tr '\n' ' '; tail -n 3 "$W/runs.log" | cut -c1-200; cat "$W/ben/ben-200.diff" 2>/dev/null; date -u +%FT%TZ

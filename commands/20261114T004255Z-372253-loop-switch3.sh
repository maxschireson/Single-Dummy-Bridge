# boxctl: timeout=600
# boxctl: timeout=600
# loop session: the collection's rollout net from v2 to round 3's (head to head round 3's net alone beat v2 alone +0.40 +-
# 0.07 and round 2's +0.19 +- 0.06 on 4,000 deals each). The sps run stops; the chain restarts on e87d09aa6e2a2ea7e496e15ef3f8c92c757fcf1d with
# stu3-psa~stu3-psb (the lead still rolled out as every other card); the row publisher moves to the new run with the
# pure-rollout ids read as stup0 (alias.txt). Boards in hand are lost, every finished board kept.
set -euo pipefail
COMMIT=e87d09aa6e2a2ea7e496e15ef3f8c92c757fcf1d
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
B=$(cat "$W/pub/.git/HEAD" 2>/dev/null | sed 's#.*rollout-loop-\(azure[0-9]\)-.*#\1#')
case "$B" in azure6) OLD=sps0c; NEW=sp3sc ;; azure2) OLD=sps0d; NEW=sp3sd ;; azure1) OLD=sps0e; NEW=sp3se ;; azure5) OLD=sps0; NEW=sp3s ;;
             *) echo "not a box for this script: $B"; exit 1 ;; esac
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
(cd "$S" && [ -f models/cardplay/stu-net-r3-20261113/policy.npz ] || bash training/rollout-loop-20261113/get_net.sh 3 a8cf8a94ebcf29da88c12d1fb26ad4b53a6322b5518905d41d961f04027428c9)
sudo systemctl stop loop-collect loop-collect-b loop-rows 2>/dev/null || true
echo "$(date -u +%FT%TZ) $OLD stopped: the collection moves to $NEW (round 3's net in the rollouts)" >> "$W/runs.log"
sudo systemctl reset-failed loop-collect loop-collect-b loop-rows 2>/dev/null || true
sudo systemd-run --unit=loop-collect --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-$B.txt"
[ "$B" = azure5 ] || sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/rows.sh" "$NEW"
sleep 20; echo "box $B: $(systemctl is-active loop-collect loop-rows loop-publish | tr '\n' ' ')"; tail -n 2 "$W/runs.log" | cut -c1-220
echo "$OLD $(wc -l < "$W/runs/$OLD/results.jsonl") tables (final)"; date -u +%FT%TZ

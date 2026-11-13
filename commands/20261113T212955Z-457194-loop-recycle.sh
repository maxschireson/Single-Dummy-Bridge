# boxctl: timeout=600
# boxctl: timeout=600
# loop session: the collection's sp0 workers grow to 3-4 GB each and boxes run out of memory (a worker is killed:
# BrokenProcessPool, the run restarts). The chains restart on 474ed8b with ~/work/loop/RECYCLE = 30: boards in rounds
# of 30 a worker, each round with fresh worker processes (gen8_match --recycle). Play is unchanged; boards in hand are
# lost, every finished board kept.
set -euo pipefail
COMMIT=474ed8bbfaa089d4eb9e08b4cb560bddffa58c01
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
free -m | sed -n 2p
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -3
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo 30 > "$W/RECYCLE"
B=$(cat "$W/pub/.git/HEAD" 2>/dev/null | sed 's#.*rollout-loop-\(azure[0-9]\)-.*#\1#')
U=loop-collect; [ "$B" = azure3 ] && U=loop-chain
sudo systemctl stop "$U" loop-collect-b 2>/dev/null || true
sudo systemctl reset-failed "$U" loop-collect-b 2>/dev/null || true
sudo systemd-run --unit="$U" --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-$B.txt"
sudo systemd-run --unit=loop-collect-b --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-${B}b.txt"
sleep 30; echo "box $B: $(systemctl is-active "$U" loop-collect-b | tr '\n' ' ')"; tail -n 2 "$W/runs.log" | cut -c1-200
free -m | sed -n 2p; date -u +%FT%TZ

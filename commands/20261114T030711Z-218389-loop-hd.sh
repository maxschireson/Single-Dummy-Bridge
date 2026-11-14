# boxctl: timeout=300
# boxctl: timeout=300
# loop session: how the simulated seats take their cards, on azure1 (rungs.sh jobs-azure1-hd.txt in a unit of its own: the
# Gen 8 record collection pauses; hd-n, the nets alone with every card drawn, then h3-p2, SiD (rollout) Stu R3 with the
# draw sharpened against the reference; the collection restarts after).
set -euo pipefail
COMMIT=fc8202fc96158f249b5ff14b3d0a2e959dbb5c7f
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
sudo systemctl reset-failed loop-rungs 2>/dev/null || true
sudo systemd-run --unit=loop-rungs --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/rungs.sh" jobs-azure1-hd.txt azure1
sleep 20; systemctl is-active loop-rungs loop-collect loop-rows | tr '\n' ' '; tail -n 2 "$W/runs.log" | cut -c1-200; echo "sg8e $(wc -l < "$W/runs/sg8e/results.jsonl" 2>/dev/null) tables so far"; date -u +%FT%TZ

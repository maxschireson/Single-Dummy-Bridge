# boxctl: timeout=300
# loop session: round 4 again on azure5, right-sized and as a unit of its own (loop-r4, round4.sh; the first try, one long
# command sized by boards, could not fit the disk and blocked the box's queue). Leftovers of the first try are stopped and
# removed; the unit trains the two nets, tests them, plays the nets-alone matches and restarts the collection. Returns at once.
set -euo pipefail
COMMIT=05cf9aec8a2989b1449d71021e068279f2ede0eb
W=$HOME/work/loop; S=$W/src; T=training/rollout-loop-20261113
tail -n 3 "$W/runs.log" | cut -c1-170
sudo systemctl stop loop-arena loop-r4 loop-rungs loop-collect loop-collect-b 2>/dev/null || true
pkill -u "$USER" -f "round2.sh|sample_set.py|merge_sets.py|gen7_build_dataset.py|train_rollout_net.py|scripts/x8_match.py" 2>/dev/null || true; sleep 3
rm -rf "$W/r4" "$W/r4c" "$W/r4arena/arena.npz" "$W/r4arena/eps_sample"
df -h --output=avail "$HOME" | tail -1; free -g | sed -n 2p; ls "$W/r4arena/eps" | wc -l; ls "$W"/in/rows-azure*/ | grep -c npz; ls "$W"/in/cut-azure*/ | grep -c npz
git -C "$S" fetch -q --depth 12 origin research/rollout-loop-20261113 && git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo "$(date -u +%FT%TZ) round 4 again, as the unit loop-r4 (round4.sh): the arena's rows from a sample, a third as many replay rows" >> "$W/runs.log"
sudo systemctl reset-failed loop-r4 2>/dev/null || true
sudo systemd-run --unit=loop-r4 --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" -- bash "$S/$T/round4.sh"
sleep 45; systemctl is-active loop-r4 loop-collect loop-publish | tr '\n' ' '; tail -n 4 "$W/r4go.log" | cut -c1-200; date -u +%FT%TZ

# boxctl: timeout=600
# boxctl: timeout=600
# sidnet: the build stage finished (set 75,390 deals, 30,367,755 rows) but its marker was written as done/s15 (a loop
# variable bug, fixed in 3c34774). Update the source, rename the marker, start the remaining stages as sidnet-run3.
set -euo pipefail
W=$HOME/work/sidnet; cd "$W/src"
git fetch -q --depth 1 origin research/sid-net-s0-20261113 && git reset -q --hard FETCH_HEAD
echo "source $(git rev-parse --short HEAD) $(git log -1 --format=%s | cut -c1-70)"
grep -q '"examples": 30367755' "$W/logs/build.log" && [ -f "$W/data/train.npz" ] && [ ! -d "$W/shards" ] || { echo "the set is not as expected"; exit 1; }
[ -f "$W/done/s15" ] && mv "$W/done/s15" "$W/done/build"
ls "$W/done" | tr "\n" " "; echo
systemctl is-active --quiet sidnet-run3 && { echo "sidnet-run3 already running"; exit 0; }
sudo systemd-run --unit=sidnet-run3 --uid="$USER" --working-directory="$W/src" --setenv=HOME="$HOME" --property=Nice=10 \
  --setenv=STAGES="buildB train e1 push" -- bash training/sid-net-s0-20261113/chain.sh
sleep 50
systemctl is-active sidnet-run3; tail -4 "$W/logs/timeline.log" | cut -c1-200; tail -1 "$W/logs/buildB.log" 2>/dev/null | cut -c1-160

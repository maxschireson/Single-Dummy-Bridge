# boxctl: timeout=120
# boxctl: timeout=120
# loop session (Max, 06:59 to 07:20 UTC: the USBC records since 2021, every category, fetched by the boxes): part 1 of 3 of the
# sessions, a request every 0.2 s, in a unit of its own (loop-usbc, Nice 10) beside the box's work. Records land in
# ~/work/loop/pub/usbc/ (test data, never trained on); the publisher pushes them with the rest of pub/. Returns at once.
set -euo pipefail
W=$HOME/work/loop; S2=$W/src-lc
[ -d "$S2/.git" ] || git clone -q --depth 5 --branch research/rollout-loop-20261113 https://github.com/maxschireson/Single-Dummy-Bridge "$S2"
git -C "$S2" fetch -q --depth 5 origin research/rollout-loop-20261113 && git -C "$S2" checkout -q 233093851269b409f9ebe1abbd517ca63534d475
mkdir -p "$W/pub/usbc"; [ -d $HOME/work/usbc/records ] && cp -n $HOME/work/usbc/records/*.json.gz "$W/pub/usbc/" 2>/dev/null || true
sudo systemctl stop loop-usbc 2>/dev/null || true; sudo systemctl reset-failed loop-usbc 2>/dev/null || true
sudo systemd-run --unit=loop-usbc --uid="$USER" --working-directory="$S2" --setenv=HOME="$HOME" --property=Nice=10 --property=StandardOutput=append:"$W/usbc.log" --property=StandardError=append:"$W/usbc.log" -- python3 "$S2/training/rollout-loop-20261113/usbc/harvest.py" "$W/pub/usbc" --part 1/3 --pause 0.2
sleep 40; systemctl is-active loop-usbc || true; tail -n 2 "$W/usbc.log" | cut -c1-160; systemctl is-active loop-publish loop-pub 2>/dev/null | tr '\n' ' '; systemctl list-units --plain --no-legend 'loop-*' | awk '{print $1}' | tr '\n' ' '; date -u +%FT%TZ

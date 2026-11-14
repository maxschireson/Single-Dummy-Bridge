# boxctl: timeout=120
# boxctl: timeout=120
# loop session (Max, 06:59 UTC: the USBC records, fetched by the boxes): the 2025 Open, Mixed and Senior USBCs, which the archive
# list leaves out (screens from USBF's bracket sheets), in a unit of its own (loop-usbc25) beside the running harvest. Returns at once.
set -euo pipefail
W=$HOME/work/loop; S3=$HOME/work/usbc/src
git -C "$S3" fetch -q --depth 3 origin research/rollout-loop-20261113 && git -C "$S3" checkout -q da6ec57afbe5a754f2e717766a22d4e98ff6866a
sudo systemctl reset-failed loop-usbc25 2>/dev/null || true
sudo systemd-run --unit=loop-usbc25 --uid="$USER" --working-directory="$S3" --setenv=HOME="$HOME" --property=Nice=10 --property=StandardOutput=append:"$W/usbc25.log" --property=StandardError=append:"$W/usbc25.log" -- python3 "$S3/training/rollout-loop-20261113/usbc/harvest.py" "$W/pub/usbc" --since 2099 --screens "$S3/training/rollout-loop-20261113/usbc/screens-2025.txt" --pause 0.2
sleep 5; systemctl is-active loop-usbc25 loop-usbc loop-usbclt | tr '\n' ' '; echo "records $(ls $W/pub/usbc/*.json.gz | wc -l)"; date -u +%FT%TZ

# boxctl: timeout=150
# g7, on azure1 (now the loop's box): close g7's stopped 8X v3 cohort and free the memory its solver cache holds. Touches only
# g7's units and files: the publisher stops after its last push, g7's 8X units are disabled, the 12 GB RAM-disk cache of the
# stopped run is emptied. The run, its failure record and the prepared follow-on cohort stay as they are.
set -u
W=$HOME/work; S=$W/gen8x; R=$W/runs/gen8-x3-azure1
date -u +%T; df -h /mnt/ddscache | tail -1; ls -la /mnt/ddscache | tail -4 | cut -c1-150
k=$(ls $R/receipts | wc -l); p=$(python3 -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" $R/publisher-status.json)
echo "receipts $k, published $p"
[ "$k" = "$p" ] || { echo "feed is behind; leaving the publisher running"; exit 0; }
touch "$R/PUBLISH_STOP"; for i in $(seq 1 24); do [ "$(systemctl is-active arena-gen8x-publish)" = active ] || break; sleep 5; done
sudo systemctl disable --now arena-gen8x-publish arena-gen8x gen8x-recycle next8x >/dev/null 2>&1
[ -e "$R/WATCHDOG_STOP" ] || echo "Stopped on 13 November 2026 at 16:32 UTC at $k of 6,000 boards, every board published: the solver cache on the 12 GB RAM disk filled ('database or disk is full', failures/003990.json, kept). azure1 went to the loop at 19:02 UTC (Max). Not resumed." > "$R/WATCHDOG_STOP"
if [ -L "$R/dds-cache.sqlite" ]; then C=$(readlink "$R/dds-cache.sqlite"); case "$C" in /mnt/ddscache/*) rm -f "$C" "$C-wal" "$C-shm";; esac; fi
df -h /mnt/ddscache | tail -1; for u in arena-gen8x arena-gen8x-publish gen8x-recycle next8x sidplay; do printf '%s=%s/%s ' $u "$(systemctl is-active $u)" "$(systemctl is-enabled $u 2>/dev/null)"; done; echo; free -g | sed -n 2p

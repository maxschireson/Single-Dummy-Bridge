# boxctl: timeout=60
# Free azure6 (Max, 18:07 UTC: an Azure box for building single-dummy lookup tables): finish the Gen 8 cohort after the boards in
# hand, publish every board, stop and disable the operator's units here. Files stay. Background unit drain8; log ~/work/gen8/drain8.log.
set -euo pipefail
[ "$BOXCTL_BOX" = azure6 ] || { echo "this command is for azure6"; exit 1; }
S=$HOME/work/gen8
cat > "$S/drain8.sh" <<'EOF_DRAIN'
#!/usr/bin/env bash
set -uo pipefail
W=$HOME/work; S=$W/gen8; PY=$W/venv/bin/python
say() { echo "$(date -u +%T) $*"; }
R=$(systemctl show -p ExecStart --value arena-gen8 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
say "draining $(basename "$R") to free the box (Max, 18:07 UTC)"
touch "$S/SWITCH_OFF" "$S/RECYCLE_OFF"
sudo systemctl stop prepnext8 >/dev/null 2>&1; sudo systemctl disable --now next8 >/dev/null 2>&1
for i in $(seq 1 120); do [ -e "$S/recycling" ] || break; sleep 5; done
sudo systemctl disable --now gen8-recycle >/dev/null 2>&1
touch "$R/STOP"
for i in $(seq 1 360); do [ "$(systemctl is-active arena-gen8)" = active ] || break; sleep 5; done
[ "$(systemctl is-active arena-gen8)" = active ] && { say "collector still running after 30 minutes"; exit 1; }
[ -z "$(ls "$R/failures")" ] || { say "failure record in $(basename "$R"): $(ls "$R/failures" | tr '\n' ' ')"; exit 1; }
k=$(ls "$R/receipts" | wc -l)
for i in $(seq 1 120); do p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null); [ "$p" = "$k" ] && break; sleep 10; done
[ "$p" = "$k" ] || { say "feed has $p of $k boards; publisher left running"; exit 1; }
touch "$R/PUBLISH_STOP"; for i in $(seq 1 30); do [ "$(systemctl is-active arena-gen8-publish)" = active ] || break; sleep 5; done
sudo systemctl disable --now arena-gen8-publish >/dev/null 2>&1; sudo systemctl disable arena-gen8 >/dev/null 2>&1
t=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['target'])" "$R/manifest.json")
[ -e "$R/WATCHDOG_STOP" ] || echo "Drained on $(date -u +%FT%TZ) at $k of $t boards, all published: azure6 was freed for another project (Max, 12 November 2026, 18:07 UTC). Its unplayed deals may be taken over by a later cohort. No watchdog ran on this box." > "$R/WATCHDOG_STOP"
if [ -L "$R/dds-cache.sqlite" ]; then T=$(readlink "$R/dds-cache.sqlite"); case "$T" in /mnt/ddscache/*) rm -f "$T" "$T-wal" "$T-shm";; esac; fi
say "finished $(basename "$R") at $k of $t boards, all published; units: $(for u in arena-gen8 arena-gen8-publish gen8-recycle next8 prepnext8; do printf '%s=%s ' $u "$(systemctl is-active $u 2>/dev/null)"; done)"
say "load $(cut -d' ' -f1-3 /proc/loadavg); memory available $(free -m | awk 'NR==2{print $7}') MB; disk free $(df -h --output=avail $HOME | tail -1 | tr -d ' ')"
say DONE
EOF_DRAIN
chmod +x "$S/drain8.sh"
systemctl is-active --quiet drain8 && { echo "drain8 already running"; exit 0; }
sudo systemctl reset-failed drain8 2>/dev/null || true
sudo systemd-run --quiet --unit=drain8 --uid="$(id -un)" --setenv=HOME="$HOME" --property=StandardOutput=append:"$S/drain8.log" --property=StandardError=append:"$S/drain8.log" -- "$S/drain8.sh"
sleep 20; echo "drain8: $(systemctl is-active drain8)"; tail -4 "$S/drain8.log" | cut -c1-240

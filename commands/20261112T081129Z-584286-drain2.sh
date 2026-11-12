# boxctl: timeout=60
# azure2 to the plan session at 08:15 UTC: drain the Gen 7.1 cohort gracefully. Background unit drain2; ~/work/gen71/drain2.log.
set -euo pipefail
S=$HOME/work/gen71
[ "$BOXCTL_BOX" = azure2 ] || { echo "this command is for azure2"; exit 1; }
cat > "$S/drain2.sh" <<'EOF_DRAIN2'
#!/usr/bin/env bash
# azure2 goes to the plan session at 08:15 UTC (Max's authority; board, 07:15 and 07:31 UTC). Drain the Gen 7.1 cohort the
# graceful way: memory supervisor off, STOP, boards in hand finish, every board published, units disabled, the RAM-disk
# solver cache emptied. Nothing in the run or its feed is deleted; its unplayed deals stay for later.
set -uo pipefail
W=$HOME/work; S=$W/gen71; PY=$W/venv/bin/python
say() { echo "$(date -u +%T) $*"; }
R=$(systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
[ -d "$R" ] || { say "no run for arena-gen71"; exit 1; }
say "draining $(basename "$R"): $(ls "$R/receipts" | wc -l) boards"
touch "$S/RECYCLE_OFF"
for i in $(seq 1 120); do [ -e "$S/recycling" ] || break; sleep 5; done
sudo systemctl disable --now gen71-recycle >/dev/null 2>&1
touch "$R/STOP"
for i in $(seq 1 240); do [ "$(systemctl is-active arena-gen71)" = active ] || break; sleep 5; done
[ "$(systemctl is-active arena-gen71)" = active ] && { say "collector still running after 20 minutes; STOP left in place"; exit 1; }
sudo systemctl disable arena-gen71 >/dev/null 2>&1
[ -z "$(ls "$R/failures")" ] || { say "failure record: $(ls "$R/failures" | tr '\n' ' ')"; exit 1; }
r=$(ls "$R/receipts" | wc -l)
for i in $(seq 1 90); do
  p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null)
  [ "$p" = "$r" ] && break; sleep 10
done
[ "$p" = "$r" ] || { say "the feed has $p of $r boards after 15 minutes; publisher left running"; exit 1; }
touch "$R/PUBLISH_STOP"
for i in $(seq 1 30); do [ "$(systemctl is-active arena-gen71-publish)" = active ] || break; sleep 5; done
sudo systemctl disable --now arena-gen71-publish >/dev/null 2>&1
if [ -L "$R/dds-cache.sqlite" ]; then T=$(readlink "$R/dds-cache.sqlite"); case "$T" in /mnt/ddscache/*) rm -f "$T" "$T-wal" "$T-shm";; esac; fi
say "drained: $r boards, published $p, feed head $(git -C "$W/publication/$(basename "$R")" rev-parse HEAD 2>/dev/null)"
say "units: arena-gen71 $(systemctl is-active arena-gen71), arena-gen71-publish $(systemctl is-active arena-gen71-publish), gen71-recycle $(systemctl is-active gen71-recycle); RAM disk $(du -sm /mnt/ddscache | cut -f1) MB"
say "memory available $(free -m | awk 'NR==2{print $7}') MB; load $(cut -d' ' -f1-3 /proc/loadavg); python processes of the arena: $(ps -eo args --no-headers | grep -c '[g]en5_runtime\|[p]ublish_gen5')"
say DONE
EOF_DRAIN2
chmod +x "$S/drain2.sh"
systemctl is-active --quiet drain2 && { echo "already running"; exit 0; }
sudo systemctl reset-failed drain2 2>/dev/null || true
sudo systemd-run --quiet --unit=drain2 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$S/drain2.log" --property=StandardError=append:"$S/drain2.log" -- "$S/drain2.sh"
sleep 10; echo "drain2: $(systemctl is-active drain2)"; tail -3 "$S/drain2.log" | cut -c1-200

# boxctl: timeout=60
# azure1: four Gen 7.1 workers while g8's matches still run here, eight when none has run for ten minutes (unit share71).
set -euo pipefail
S=$HOME/work/gen71
[ "$BOXCTL_BOX" = azure1 ] || { echo "this command is for azure1"; exit 1; }
date -u +%T; echo "go71d $(systemctl is-active go71d); arena-gen71 $(systemctl is-active arena-gen71)"; tail -4 "$S/go71d.log" | cut -c1-300
[ "$(systemctl is-active arena-gen71)" = active ] || { echo "the collector is not running yet; nothing done"; exit 0; }
cat > "$S/share71.sh" <<'EOF_SHARE'
#!/usr/bin/env bash
# Unit share71 (azure1): the Gen 7.1 collector runs four workers while g8's matches (scripts/gen8_match.py) still run on this box;
# when none has run for ten minutes it goes to eight workers (graceful restart of the same cohort) and this unit ends.
set -uo pipefail
W=$HOME/work; S=$W/gen71
say() { echo "$(date -u +%FT%TZ) $*"; }
R=$(systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
restart_with() {
  touch "$S/RECYCLE_OFF"; for i in $(seq 1 120); do [ -e "$S/recycling" ] || break; sleep 5; done
  touch "$R/STOP"; for i in $(seq 1 360); do [ "$(systemctl is-active arena-gen71)" = active ] || break; sleep 5; done
  [ "$(systemctl is-active arena-gen71)" = active ] && { say "collector did not stop; STOP left in place"; rm -f "$S/RECYCLE_OFF"; return 1; }
  [ -z "$(ls "$R/failures")" ] || { say "failure record; left stopped"; return 1; }
  echo "WORKERS=$1" > "$S/workers.env"; rm -f "$R/STOP"; sudo systemctl reset-failed arena-gen71 2>/dev/null; sudo systemctl start arena-gen71; rm -f "$S/RECYCLE_OFF"
  say "collector $(systemctl is-active arena-gen71) with $1 workers, $(ls "$R/receipts" | wc -l) boards done"
}
if [ "$(grep -o '[0-9]*' "$S/workers.env")" != 4 ] && pgrep -f scripts/gen8_match.py >/dev/null; then say "g8's matches are running: going to four workers"; restart_with 4 || exit 1; fi
quiet=0
while true; do
  if pgrep -f scripts/gen8_match.py >/dev/null; then quiet=0; else quiet=$((quiet+1)); fi
  if [ "$quiet" -ge 5 ]; then say "no g8 match for ten minutes: going to eight workers"; restart_with 8; exit 0; fi
  sleep 120
done
EOF_SHARE
chmod +x "$S/share71.sh"
systemctl is-active --quiet share71 && { echo "share71 already running"; exit 0; }
sudo systemctl reset-failed share71 2>/dev/null || true
sudo systemd-run --quiet --unit=share71 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$S/share71.log" --property=StandardError=append:"$S/share71.log" -- "$S/share71.sh"
sleep 5; echo "share71: $(systemctl is-active share71)"; tail -2 "$S/share71.log" 2>/dev/null | cut -c1-200

# boxctl: timeout=120
# azure2: move the Gen 7.1 cohort's shared solver cache to a RAM disk (the workers wait on its fsyncs and write lock about a
# third of the time). Graceful restart of the same cohort; nothing in it changes. The memory supervisor empties the RAM-disk
# cache at each of its restarts. Background unit cachefix; progress in ~/work/gen71/cachefix.log.
set -euo pipefail
W=$HOME/work; S=$W/gen71
[ "$BOXCTL_BOX" = azure2 ] || { echo "this command is for azure2"; exit 1; }
cat > "$S/cachefix.sh" <<'EOF_CACHEFIX'
#!/usr/bin/env bash
# azure2: the eight workers of the Gen 7.1 cohort spend about a third of their time waiting on the shared solver cache
# (dds-cache.sqlite in the run folder: WAL with synchronous=FULL, so every solve batch commits with an fsync, and eight
# processes share one write lock). This puts the cache on a RAM disk (tmpfs /mnt/ddscache, also in /etc/fstab so it exists
# after a reboot, empty): the collector is stopped the graceful way, the disk cache is kept beside the run under another
# name, an empty cache is created on the RAM disk and linked at the path the runtime uses, and the same cohort starts again.
# Nothing in the cohort, its bots or its records changes; a cache entry is an exact solver result, so it changes timing only.
set -uo pipefail
W=$HOME/work; S=$W/gen71; PY=$W/venv/bin/python; M=/mnt/ddscache
say() { echo "$(date -u +%T) $*"; }
R=$(systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1)
[ -d "$R" ] || { say "no run for arena-gen71"; exit 1; }
say "run $(basename "$R"), $(ls "$R/receipts" | wc -l) boards"
if ! mountpoint -q $M; then
  sudo mkdir -p $M && sudo mount -t tmpfs -o size=12G,mode=0700,uid=$(id -u),gid=$(id -g),nosuid,nodev tmpfs $M || { say "could not mount the RAM disk"; exit 1; }
fi
grep -q " $M tmpfs " /etc/fstab || echo "tmpfs $M tmpfs size=12G,mode=0700,uid=$(id -u),gid=$(id -g),nosuid,nodev 0 0" | sudo tee -a /etc/fstab >/dev/null
say "RAM disk: $(df -h $M | tail -1 | awk '{print $2 " size, " $4 " free"}'); fstab: $(grep -c " $M tmpfs " /etc/fstab) line"
touch "$S/RECYCLE_OFF"
for i in $(seq 1 120); do [ -e "$S/recycling" ] || break; sleep 5; done
touch "$R/STOP"
for i in $(seq 1 240); do [ "$(systemctl is-active arena-gen71)" = active ] || break; sleep 5; done
[ "$(systemctl is-active arena-gen71)" = active ] && { say "collector still running after 20 minutes; STOP left in place"; exit 1; }
[ -z "$(ls "$R/failures")" ] || { say "failure record: $(ls "$R/failures" | tr '\n' ' '); left stopped"; exit 1; }
say "collector stopped with $(ls "$R/receipts" | wc -l) boards"
C=$R/dds-cache.sqlite; T=$M/$(basename "$R").sqlite
if [ -L "$C" ]; then say "the cache is already a link to $(readlink "$C")"; else
  "$PY" -c "import sqlite3,sys; db=sqlite3.connect(sys.argv[1],timeout=60); db.execute('PRAGMA wal_checkpoint(TRUNCATE)'); db.close()" "$C"
  stamp=$(date -u +%Y%m%dT%H%M%SZ)
  for f in "$C" "$C-wal" "$C-shm"; do [ -e "$f" ] && mv "$f" "$R/dds-cache.disk-$stamp.sqlite${f#$C}"; done
  say "disk cache kept as $(ls "$R" | grep "dds-cache.disk-$stamp" | tr '\n' ' ')($(du -m "$R/dds-cache.disk-$stamp.sqlite" | cut -f1) MB)"
  rm -f "$T" "$T-wal" "$T-shm"
  "$PY" - "$T" <<'PYEOF'
import sqlite3, sys
db = sqlite3.connect(sys.argv[1], timeout=60)
db.execute('PRAGMA journal_mode=WAL')
db.execute('PRAGMA synchronous=FULL')
db.execute('CREATE TABLE IF NOT EXISTS positions (solver BLOB NOT NULL, position BLOB NOT NULL, scores BLOB NOT NULL,PRIMARY KEY(solver,position)) WITHOUT ROWID')
db.commit(); db.close()
PYEOF
  ln -s "$T" "$C"
  say "cache now $C -> $(readlink "$C")"
fi
rm -f "$R/STOP"; sudo systemctl reset-failed arena-gen71 2>/dev/null; sudo systemctl start arena-gen71
rm -f "$S/RECYCLE_OFF"
say "collector $(systemctl is-active arena-gen71); memory supervisor $(systemctl is-active gen71-recycle)"
sleep 150
say "files on the RAM disk: $(ls $M | tr '\n' ' '); in the run: $(ls "$R" | grep dds-cache | tr '\n' ' ')"
pid=$(systemctl show -p MainPID --value arena-gen71); tick=$(getconf CLK_TCK)
work=$(for k in $(ps -o pid= --ppid $pid); do [ "$(ps -o rss= -p $k)" -gt 200000 ] && echo $k; done)
declare -A a; for w in $work; do a[$w]=$(awk '{print $14+$15}' /proc/$w/stat); done; vm0=$(head -1 /proc/stat); t0=$(date +%s.%N)
sleep 30
el=$(echo "$(date +%s.%N) - $t0" | bc); tot=0; n=0
for w in $work; do d=$(( $(awk '{print $14+$15}' /proc/$w/stat) - ${a[$w]} )); tot=$(( tot + $(echo "scale=0; 100*$d/$tick/$el" | bc) )); n=$((n+1)); done
echo "$vm0" "$(head -1 /proc/stat)" | awk -v tot=$tot -v n=$n '{u=$13-$2; nn=$14-$3; s=$15-$4; i=$16-$5; w=$17-$6; t=u+nn+s+i+w+($18-$7)+($19-$8); printf "after the move: %d workers at %d%% of %d%%; system idle %.0f%%, iowait %.1f%%\n", n, tot, 100*n, 100*i/t, 100*w/t}'
say DONE
EOF_CACHEFIX
cat > /tmp/recycle_patch.py <<'EOF_PATCH'
import sys
p = sys.argv[1]; s = open(p).read()
a = '''  rm -f "$R/STOP"; sudo systemctl reset-failed arena-gen71 2>/dev/null; sudo systemctl start arena-gen71'''
b = '''  # A cache on the RAM disk is emptied at each restart: entries are exact solver results for positions of boards already
  # finished, and a new deal almost never reaches the same position, so this bounds the memory it takes.
  if [ -L "$R/dds-cache.sqlite" ]; then T=$(readlink "$R/dds-cache.sqlite"); case "$T" in /mnt/ddscache/*) say "emptying the RAM-disk cache ($(du -m "$T" | cut -f1) MB)"; rm -f "$T" "$T-wal" "$T-shm"
    "$HOME/work/venv/bin/python" -c "import sqlite3,sys; db=sqlite3.connect(sys.argv[1],timeout=60); db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=FULL'); db.execute('CREATE TABLE IF NOT EXISTS positions (solver BLOB NOT NULL, position BLOB NOT NULL, scores BLOB NOT NULL,PRIMARY KEY(solver,position)) WITHOUT ROWID'); db.commit(); db.close()" "$T";; esac; fi
  rm -f "$R/STOP"; sudo systemctl reset-failed arena-gen71 2>/dev/null; sudo systemctl start arena-gen71'''
if b in s: print('already patched'); sys.exit()
assert s.count(a) == 1, s.count(a)
open(p, 'w').write(s.replace(a, b)); print('patched')
EOF_PATCH
python3 /tmp/recycle_patch.py "$S/recycle71.sh"; bash -n "$S/recycle71.sh" && echo "recycle71.sh parses"
sudo systemctl restart gen71-recycle; echo "gen71-recycle $(systemctl is-active gen71-recycle)"
chmod +x "$S/cachefix.sh"
systemctl is-active --quiet cachefix && { echo "already running"; exit 0; }
sudo systemctl reset-failed cachefix 2>/dev/null || true
sudo systemd-run --quiet --unit=cachefix --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$S/cachefix.log" --property=StandardError=append:"$S/cachefix.log" -- "$S/cachefix.sh"
sleep 20; echo "cachefix: $(systemctl is-active cachefix)"; tail -5 "$S/cachefix.log" | cut -c1-240

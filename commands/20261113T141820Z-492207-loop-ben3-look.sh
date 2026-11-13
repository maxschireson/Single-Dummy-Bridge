# boxctl: timeout=120
# boxctl: timeout=120
# loop session: how the arena's lanes on azure3 ran matches against the BEN (64) servers (read-only), to run Stu against
# BEN as Max asked (11:30 UTC).
W=$HOME/work
ls "$W/lanes" 2>/dev/null | head -30
systemctl list-units --all 'ben-server@*' 'lane*' --no-legend 2>/dev/null | cut -c1-110 | head -14
systemctl cat ben-server@1 2>/dev/null | grep -v '^#' | cut -c1-240 | head -20
for f in "$W"/lanes/*.sh "$W"/lanes/*/run.sh "$W"/lanes/*/*.sh; do [ -f "$f" ] && { echo "== $f"; grep -n "ben\|gen8_match\|x8_match\|--pair\|--bots\|--source\|url\|port" "$f" | cut -c1-230 | head -14; }; done 2>/dev/null | head -80
ls "$W"/lanes/*/ 2>/dev/null | head -30
grep -rl '"ben' "$W"/lanes --include='*.json' 2>/dev/null | head -5
ss -ltnp 2>/dev/null | grep -i "python\|ben" | cut -c1-140 | head -10
date -u +%FT%TZ

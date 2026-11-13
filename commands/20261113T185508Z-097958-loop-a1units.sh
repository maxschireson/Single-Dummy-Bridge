# boxctl: timeout=120
# boxctl: timeout=120
# loop session: g7's 8X units on azure1 and how they are stopped (read-only).
for u in arena-gen8x arena-gen8x-publish gen8x-recycle next8x; do echo "== $u: $(systemctl is-active $u) / $(systemctl is-enabled $u 2>/dev/null)"; systemctl cat $u 2>/dev/null | grep -v '^#' | grep "ExecStart\|ExecStartPre\|Description\|Restart=" | cut -c1-250; done
journalctl -u arena-gen8x --no-pager -n 4 2>/dev/null | cut -c1-200
journalctl -u next8x --no-pager -n 3 2>/dev/null | cut -c1-200
journalctl -u gen8x-recycle --no-pager -n 3 2>/dev/null | cut -c1-200
ls ~/work/gen8x | head -30 | tr '\n' ' '; echo
for f in ~/work/gen8x/*.sh; do [ -f "$f" ] && { echo "-- $f"; grep -n "STOP\|OFF\|while\|sleep\|systemctl" "$f" | cut -c1-200 | head -12; }; done
ls ~/work/runs/gen8-x3n-azure1 2>/dev/null | tr '\n' ' '; echo; cat ~/work/runs/gen8-x3n-azure1/state.json 2>/dev/null | head -c 300; echo
ls ~/work/runs/gen8-x3-azure1 | grep -i stop; date -u +%FT%TZ; date +%s

# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): how azure3's BEN lanes are run, for a BEN (200) setting beside them (Max, 23:31 UTC).
systemctl cat ben-server@1 2>/dev/null | sed -n 1,40p
for n in 1 2; do systemctl is-active ben-server@$n; done
ps -eo rss,args | grep -i "[b]en" | grep -v boxctl | head -4 | cut -c1-220
free -m | sed -n 2p

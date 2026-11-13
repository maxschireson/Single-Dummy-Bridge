# boxctl: timeout=900
# boxctl: timeout=900
# sidplay: open the play server to the internet (Max, 13 Nov 05:58 UTC: azure1, public, label play-sid).
set -euo pipefail
OUT=$(bash /opt/sidplay/app/play/deploy/expose.sh Bridgebots play-sid)
echo "$OUT"
FQDN=$(echo "$OUT" | awk '/^fqdn/{print $2}')
for i in $(seq 1 24); do getent hosts "$FQDN" >/dev/null && break; sleep 5; done
bash /opt/sidplay/app/play/deploy/caddy.sh "$FQDN"

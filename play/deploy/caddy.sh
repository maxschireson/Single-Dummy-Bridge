#!/usr/bin/env bash
# Serve the play server over HTTPS with Caddy (automatic Let's Encrypt certificate). Run on the host box after
# expose.sh has opened ports 80/443 and set the DNS name.
#
#   bash caddy.sh FQDN            e.g. bash caddy.sh sid-bridge.eastus.cloudapp.azure.com
set -euo pipefail
FQDN=${1:?host name}
if ! command -v caddy >/dev/null; then
  sudo apt-get update -q
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -q caddy
fi
sudo tee /etc/caddy/Caddyfile >/dev/null <<EOF
$FQDN {
	encode gzip
	header Strict-Transport-Security "max-age=31536000"
	reverse_proxy 127.0.0.1:8090
}
EOF
sudo systemctl enable caddy >/dev/null 2>&1
sudo systemctl restart caddy
sudo sed -i 's/^SIDPLAY_SECURE_COOKIES=.*/SIDPLAY_SECURE_COOKIES=1/' /etc/sidplay.env
sudo systemctl restart sidplay
for i in $(seq 1 30); do
  if curl -fsS "https://$FQDN/api/health" 2>/dev/null; then echo; echo "https://$FQDN is up"; exit 0; fi
  sleep 5
done
echo "HTTPS did not come up"; sudo journalctl -u caddy -n 40 --no-pager; exit 1

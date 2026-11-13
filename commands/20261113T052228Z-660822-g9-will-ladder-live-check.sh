# boxctl: timeout=60
B=https://maxschireson.github.io/Single-Dummy-Bridge/arena; for f in "index.html" "ladder.js?v=g9-ladder-20261113b" "ladder.json?v=1"; do code=$(curl -s -o /tmp/g9chk -w "%{http_code}" "$B/$f"); echo "$f $code $(sha256sum /tmp/g9chk | cut -c1-16) $(wc -c < /tmp/g9chk)"; done; curl -s "$B/index.html" | grep -n "ladder" | cut -c1-120

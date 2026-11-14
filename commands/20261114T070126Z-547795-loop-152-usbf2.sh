# boxctl: timeout=180
# boxctl: timeout=180
# loop session (read-only, a few small requests): USBF's bracket page and LoveBridge's vugraph pages for a match, to find the records.
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
get() { curl -sS -L -m 30 -A "$UA" -o "$2" -w "%{http_code} %{size_download} %{content_type} $1\n" "$1"; }
python3 - <<'PY'
import re
h = open('rr.html', encoding='utf-8', errors='replace').read()
i = h.lower().find('bidding')
print(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' | ', h[max(0, i - 1500):i + 1500]))[:2500])
PY
get "https://usbf.org/docs/vugraphs/SUSBC2025_USA2/Bracket.php?stage=QuarterFinal" br.html
grep -o -i -E "href=\"[^\"]+\"" br.html | grep -v -E "index.php|favicon|openskyweb" | sort -u | head -30
get "https://vugraph.lovebridge.com/screen/usbc/631412?screen=running-score" vg.html
grep -o -E "(src|href)=\"[^\"]+\"" vg.html | grep -v -E "icon|googl|doubleclick" | head -12
head -c 600 vg.html; echo

# boxctl: timeout=180
# boxctl: timeout=180
# loop session (Max, 06:59 UTC on 14 November: the USBC play records since 2021, fetched by a box; he chose the Azure boxes):
# a look at how USBF's bidding & play records and LoveBridge's statistics are served. Read-only, a few small requests.
set -uo pipefail
D=$HOME/work/usbc; mkdir -p $D/probe; cd $D/probe
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
get() { curl -sS -L -m 30 -A "$UA" -o "$2" -w "%{http_code} %{size_download} $1\n" "$1"; }
get "https://usbf.org/docs/vugraphs/SUSBC2025_USA2/RRsheet.php?stage=RR2" rr.html
grep -o -i -E "href=\"[^\"]+\"" rr.html | sort -u | head -40
echo ----; get "https://usbf.org/docs/vugraphs/" idx.html; grep -o -i -E "href=\"[^\"]+\"" idx.html | head -80 | tr '\n' ' '; echo
echo ----; get "https://stats.lovebridge.com/statistics/usbf_835877" lb.html; grep -o -E "(src|href)=\"[^\"]+\"" lb.html | head -20
for js in $(grep -o -E "src=\"[^\"]+\.js\"" lb.html | sed 's/src="//;s/"$//' | head -4); do
  u=$js; case $u in http*) ;; /*) u="https://stats.lovebridge.com$u" ;; *) u="https://stats.lovebridge.com/$u" ;; esac
  get "$u" "$(basename "$u")"; grep -o -E "\"(/api|https?://[a-z0-9.-]*lovebridge[a-z0-9./-]*)[^\"]{0,80}\"" "$(basename "$u")" | sort -u | head -30
done

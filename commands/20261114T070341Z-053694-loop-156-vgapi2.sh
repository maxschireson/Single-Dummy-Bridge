# boxctl: timeout=180
# boxctl: timeout=180
# loop session (read-only): every archive endpoint in the vugraph script, then the ones that may carry a table's auction and play.
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
grep -o -E "/api/[a-zA-Z/-]+" vg.js | sort | uniq -c | sort -rn | awk '{print $2}' | tr '\n' ' '; echo
grep -o -E ".{120}/api/archive/(game|table|deal|play|record|lin|pbn|search-table|score-card)[^\`\"]{0,80}.{60}" vg.js | head -8
M=usbc_397454_2_1
for p in "running-scores/$M" "registrations/$M" "teams/$M" "operators/$M" "cross-table/$M/0" "search-table/$M/1"; do
  curl -sS -m 30 -A "$UA" "$B/api/archive/$p" -o t.json -w "%{http_code} %{size_download} $p\n"; head -c 700 t.json; echo
done

# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only): what the vugraph script passes as `ns` to the watch endpoint, and a few tries.
set -uo pipefail
D=$HOME/work/usbc/probe; cd $D
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
grep -o -E ".{100}path:\"[^\"]*(watch|kibitz|table)[^\"]*\".{100}" vg.js | head -6
grep -o -E "otherTableNsId\(\)\{.{300}" vg.js | head -2
grep -o -E ".{80}(nsId|tableNsId|\.ns=)[^;]{0,120}" vg.js | head -8
M=usbc_397454_2_1
for ns in 0 1 2 3 4 400345 400346 "1-1" "1_1" "OP" "CL" "o1" "c1"; do printf '%s ' "$ns"; curl -sS -m 20 -A "$UA" "$B/api/archive/watch/$M/$ns/1" -o w_$ns.json -w "%{http_code} %{size_download}\n"; done

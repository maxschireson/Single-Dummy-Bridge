# boxctl: timeout=300
# boxctl: timeout=300
# loop session (read-only, small requests): LoveBridge vugraph sessions usbc_<id>_1_1 near the 2026 statistics id (835877).
set -uo pipefail
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
out=$HOME/work/usbc/scan2026.txt; : > $out
for id in $(seq 835600 836200); do
  n=$(curl -sS -m 10 -A "$UA" "$B/api/archive/boards/usbc_${id}_1_1" 2>/dev/null | head -c 20000 | grep -o '"boardNumber"' | wc -l)
  [ "$n" -gt 0 ] && echo "$id $n" | tee -a $out
  sleep 0.1
done
echo "found $(wc -l < $out)"

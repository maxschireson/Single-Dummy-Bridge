# boxctl: timeout=120
# boxctl: timeout=120
# loop session (read-only, a few requests): how USBF's 2026 round-robin sheet links its matches.
set -uo pipefail
cd $HOME/work/usbc/probe; UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
for u in "https://usbf.org/docs/vugraphs/USBC2026_USA1/RRsheet.php?stage=RR1" "https://usbf.org/docs/vugraphs/USBC2026_USA1/Bracket.php?stage=Final" "https://usbf.org/docs/vugraphs/MUSBC2026_USA1/Bracket.php?stage=Final" "https://usbf.org/docs/vugraphs/USBC2024/RRsheet.php?stage=RR1" "https://usbf.org/docs/vugraphs/USBC2024_USA1/RRsheet.php?stage=RR1"; do
  code=$(curl -sS -m 20 -A "$UA" -o r.html -w "%{http_code} %{size_download}" "$u"); echo "== $code $u"
  grep -o -i -E "(href|src)=\"[^\"]+\"" r.html | grep -i -E "lovebridge|vugraph|realbridge|bbo|lin|\.php" | sort -u | head -12
done

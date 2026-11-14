# boxctl: timeout=150
# boxctl: timeout=150
# loop session (read-only, a few requests): links on USBF's 2024, 2025 and 2026 results pages to brackets and vugraph folders.
set -uo pipefail
cd $HOME/work/usbc/probe; UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
for u in https://usbf.org/2024-united-states-bridge-championships/2024-usbc-results https://usbf.org/2026-usbcs/2026-usbcs-results https://usbf.org/2025-usbcs/2025-usbc-results https://usbf.org/2026-usbcs https://usbf.org/2025-usbcs; do
  code=$(curl -sS -L -m 20 -A "$UA" -o r.html -w "%{http_code}" "$u"); echo "== $code $u"
  grep -o -E 'href="[^"]+"' r.html | sed 's/href="//;s/"$//' | grep -i -E "vugraph|docs/|bracket|result|lovebridge|RRsheet" | grep -v -E "favicon|media/|\.css" | sort -u | head -25
done

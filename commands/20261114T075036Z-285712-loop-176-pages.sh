# boxctl: timeout=150
# boxctl: timeout=150
# loop session (read-only, a few requests): what USBF's 2026 bracket and round-robin pages and its past-tournaments pages link.
set -uo pipefail
cd $HOME/work/usbc/probe; UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
for u in https://usbf.org/2026-usbcs/bracket https://usbf.org/2026-usbcs/bracket-2 https://usbf.org/2026-usbcs/qualification-stage-round-robin-results https://usbf.org/2026-usbcs/usbc-round-robin-vugraph-for-first-2-matches https://usbf.org/past-tournaments; do
  code=$(curl -sS -L -m 20 -A "$UA" -o r.html -w "%{http_code} %{size_download}" "$u"); echo "== $code $u"
  grep -o -E '(href|src)="[^"]+"' r.html | sed -E 's/(href|src)="//;s/"$//' | grep -v -E "favicon|/media/|\.css|\.js|past-tournaments/20(1|20|21)|jlall|invitational|transatlantic" | grep -i -E "vugraph|docs|lovebridge|bracket|2024|2025|2026|usbc|pdf|iframe" | sort -u | head -30
  grep -o -i -E "<iframe[^>]+>" r.html | head -3
done

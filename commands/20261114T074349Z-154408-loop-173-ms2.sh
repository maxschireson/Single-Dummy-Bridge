# boxctl: timeout=200
# boxctl: timeout=200
# loop session (read-only, small requests): the archive list's date range; the live list; folder names for the 2024 and 2026 USBCs.
set -uo pipefail
cd $HOME/work/usbc/probe; UA="Mozilla/5.0 (research; USBF records for bot evaluation)"; B=https://vugraph.lovebridge.com
python3 -c "
import json; ms=json.load(open('ms.json')); d=sorted(m['startDateTime'][:7] for m in ms); print('archive list', d[0], d[-1], len(ms))
import collections; print(collections.Counter(m['miniSessionId'].split('_')[0] for m in ms if m['startDateTime']>='2024').most_common(12))"
curl -sS -m 30 -A "$UA" "$B/api/minisessions" -o live.json -w "%{http_code} %{size_download} minisessions\n"; head -c 300 live.json; echo
for d in USBC2026 USBC2026_Open OUSBC2026 Open2026 MUSBC2026 MUSBC2026_1 USBC2024 USBC2024_Open OUSBC2024_USA1 USBC2025_USA1 USBC2025 OUSBC2025 OPEN2025_USA1 OUSBC2025_USA1 JUSBC2024 JUSBC2025; do
  for page in "RRsheet.php?stage=RR1" "Bracket.php?stage=Final"; do
    code=$(curl -sS -m 15 -A "$UA" -o p.html -w "%{http_code}" "https://usbf.org/docs/vugraphs/$d/$page")
    ids=$(grep -o -E "screen/usbc/[0-9]+" p.html | grep -o -E "[0-9]+$" | sort -u | tr '\n' ' ')
    [ -n "$ids" ] && echo "$d $page $ids"
  done
done
curl -sS -m 20 -A "$UA" "https://usbf.org/docs/2025USBCs/" -o l.html -w "%{http_code} docs/2025USBCs\n"; grep -o -E 'href="[^"]+"' l.html | head -20 | tr '\n' ' '

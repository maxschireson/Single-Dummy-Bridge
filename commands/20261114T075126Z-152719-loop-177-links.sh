# boxctl: timeout=200
# boxctl: timeout=200
# loop session (read-only, small requests): USBF's 2026 "links to complete bidding and play records" page, and vugraph folders
# named like USBC2026_USA1 for 2024 to 2026, with the LoveBridge screens they link.
set -uo pipefail
cd $HOME/work/usbc/probe; UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
curl -sS -L -m 20 -A "$UA" -o r.html "https://usbf.org/2026-usbcs/links-to-complete-bidding-and-play-records"
grep -o -E '(href|src)="[^"]+"' r.html | sed -E 's/(href|src)="//;s/"$//' | grep -i -E "vugraph|lovebridge|docs/v" | sort -u | head -40
out=$HOME/work/usbc/screens.txt
for y in 2024 2025 2026; do for e in USBC MUSBC SUSBC WUSBC JUSBC OUSBC; do for suf in "" _USA1 _USA2; do d="$e$y$suf"
  for page in "RRsheet.php?stage=RR1" "Bracket.php?stage=Final" "Bracket.php?stage=QuarterFinal"; do
    h=$(curl -sS -m 15 -A "$UA" "https://usbf.org/docs/vugraphs/$d/$page" 2>/dev/null)
    ids=$(echo "$h" | grep -o -E "screen/usbc/[0-9]+" | grep -o -E "[0-9]+$" | sort -u | tr '\n' ' ')
    [ -n "$ids" ] && echo "$d $page $ids" | tee -a $out
  done; done; done; done 2>/dev/null | sort -u

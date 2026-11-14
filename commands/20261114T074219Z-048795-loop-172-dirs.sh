# boxctl: timeout=280
# boxctl: timeout=280
# loop session (read-only, small requests): USBF vugraph event folders for 2022 to 2026 and the LoveBridge screens they link.
set -uo pipefail
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
out=$HOME/work/usbc/screens.txt; : > $out
for y in 2024 2025 2026 2022 2023; do
  for e in OUSBC SUSBC MUSBC WUSBC JUSBC; do
    for suf in "" _USA1 _USA2; do
      d="${e}${y}${suf}"
      for page in "RRsheet.php?stage=RR1" "Bracket.php?stage=Final"; do
        h=$(curl -sS -m 15 -A "$UA" "https://usbf.org/docs/vugraphs/$d/$page" 2>/dev/null)
        ids=$(echo "$h" | grep -o -E "vugraph\.lovebridge\.com/screen/usbc/[0-9]+" | grep -o -E "[0-9]+$" | sort -u | tr '\n' ' ')
        [ -n "$ids" ] && echo "$d $page $ids" >> $out
      done
    done
  done
done
cat $out; echo "folders with screens: $(cut -d' ' -f1 $out | sort -u | tr '\n' ' ')"

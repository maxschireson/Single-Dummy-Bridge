# boxctl: timeout=300
# boxctl: timeout=300
# loop session (read-only, small requests): which USBF vugraph event folders exist for 2022 to 2026, and the LoveBridge screens
# their bracket and round-robin pages link (the archive list stops at 2023).
set -uo pipefail
UA="Mozilla/5.0 (research; USBF records for bot evaluation)"
out=$HOME/work/usbc/screens.txt; : > $out
for y in 2022 2023 2024 2025 2026; do
  for e in OUSBC SUSBC WUSBC MUSBC JUSBC USBC OSBC; do
    for suf in "" _USA1 _USA2 _1 _2; do
      d="${e}${y}${suf}"
      for page in "RRsheet.php?stage=RR1" "Bracket.php?stage=Final" "Bracket.php?stage=QuarterFinal" "Bracket.php?stage=SemiFinal" "Bracket.php?stage=RoundOf16"; do
        h=$(curl -sS -m 20 -A "$UA" "https://usbf.org/docs/vugraphs/$d/$page" 2>/dev/null)
        ids=$(echo "$h" | grep -o -E "vugraph\.lovebridge\.com/screen/usbc/[0-9]+" | grep -o -E "[0-9]+$" | sort -u | tr '\n' ' ')
        [ -n "$ids" ] && echo "$d $page $ids" | tee -a $out
        sleep 0.2
      done
    done
  done
done
echo "folders with screens: $(cut -d' ' -f1 $out | sort -u | tr '\n' ' ')"

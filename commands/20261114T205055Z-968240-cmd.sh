# boxctl: timeout=900
# loop session (Max, 20:49 UTC: reallocate collection boxes to the training and rollout recipes): azure1's Gen 8 collection
# stops; a quick check of bench/seat_variants.py --set horizon on 3 boards of round 3's gate records (fetched from azure3's
# transfer branch? no: azure3 holds them); here on azure1's own self-play records of the one-net bot is not available, so the
# bench reads azure1's sg8 records? No — rollout decisions are needed: this box has none. See the note at the end.
set -uo pipefail
W=$HOME/work/loop
ls $W/runs | grep -E "^(sp|bu|l3|h3|xh)" | head -20 | tr '\n' ' '; echo
du -sh $W/runs/* 2>/dev/null | sort -h | tail -5

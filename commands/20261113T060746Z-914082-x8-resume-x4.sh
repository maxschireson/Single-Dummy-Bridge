# boxctl: timeout=400
# boxctl: timeout=400
# x8 session, azure6 (Max, 06:05 UTC: was there an original 8X stronger than 8, what did I break?). The only 8X run ahead of
# Gen 8 was x4 (8x1-ft1, uniform mixing: +0.60 +- 0.29 on 77 boards), replaced after 16 minutes by x5 (8x2-ft1, mixing tempered
# by the net). The two bots differ only in the mixing powers. Stop x5 (540 boards, resumable) and resume x4 on its four
# workers, so x4 - x5 is paired on the same deals. Run from src2 (0bcdbc2): at power 0 its code draws exactly as 5ec36f1 did.
set -euo pipefail
W=$HOME/work/x8
sudo systemctl stop x8-queue6 2>/dev/null || true
pkill -f -- "--out $W/runs/x5" || true
sleep 4
sudo systemctl reset-failed x8-queue6 2>/dev/null || true
echo "$(date -u +%FT%TZ) x5 stopped at $(wc -l < $W/runs/x5/results.jsonl) boards; x4 resumes on its workers from src2 0bcdbc2 (same draws at power 0), Max 06:05" >> "$W/queue.log"
sed -e 's#x5 (8x2-ft1~8p-32-v41#x4 (8x1-ft1~8p-32-v41, resumed#' -e 's#--pair 8x2-ft1~8p-32-v41#--pair 8x1-ft1~8p-32-v41#' \
    -e 's#runs/x5#runs/x4#g' -e 's#end x5#end x4#' "$W/queue6.sh" > "$W/queue8.sh"
chmod +x "$W/queue8.sh"; grep -n "x4\|src" "$W/queue8.sh"
sudo systemd-run --unit=x8-queue8 --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue8.sh"
sed -i "s#x4: 8x1-ft1 (the same with uniform mixing, 5ec36f1; stopped)#x4: 8x1-ft1 (the same with uniform mixing, 5ec36f1; stopped at 77 boards, resumed at 06:1x from 0bcdbc2, same draws; x5 stopped then at 540)#" "$W/publish.sh"
sudo systemctl restart x8-publish
sleep 90
systemctl is-active x8-queue7 x8-queue8 x8-publish; tail -3 "$W/queue.log"; tail -1 "$W/runs/x4.log" | cut -c1-160
ps -eo args | grep "[x]8_match.py" | grep -o "runs/[a-z0-9]*" | sort | uniq -c; uptime

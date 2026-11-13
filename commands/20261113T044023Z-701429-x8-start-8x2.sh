# boxctl: timeout=600
# boxctl: timeout=600
# x8 session, azure6 (Max, 04:33 UTC): mix equal cards only where the net has no clear preference. 8x2-ft1 (0bcdbc2) = 8x1-ft1
# with card x played in proportion to p(x) ** power (2 declaring side, 3 defenders). Stop x4 (8x1-ft1, uniform mixing; partial
# record) and give its four workers to x5 = 8x2-ft1~8p-32-v41, same deals (seed 131), from src2 moved to 0bcdbc2. z3/z5 untouched.
set -euo pipefail
COMMIT=0bcdbc21289af0ce56e6ae689eeb08fa0f20f9d1
W=$HOME/work/x8; S2=$W/src2
sudo systemctl stop x8-queue5 2>/dev/null || true
pkill -f -- "--out $W/runs/x4" || true
sleep 4
sudo systemctl reset-failed x8-queue5 2>/dev/null || true
echo "$(date -u +%FT%TZ) x4 stopped at $(wc -l < $W/runs/x4/results.jsonl) boards (x5 replaces it: mixing tempered by the net, Max 04:33)" >> "$W/queue.log"
git -C "$S2" fetch -q --depth 5 origin feature/gen8x-rollout-bot-20261113 && git -C "$S2" checkout -q "$COMMIT"
git -C "$S2" log -1 --format='src2 %h %s' | cut -c1-100
sed -e 's#x4 (8x1-ft1~8p-32-v41#x5 (8x2-ft1~8p-32-v41#' -e 's#--pair 8x1-ft1~8p-32-v41#--pair 8x2-ft1~8p-32-v41#' \
    -e 's#runs/x4#runs/x5#g' -e 's#end x4#end x5#' "$W/queue5.sh" > "$W/queue6.sh"
chmod +x "$W/queue6.sh"; grep -n "x5\|x4" "$W/queue6.sh"
sudo systemd-run --unit=x8-queue6 --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue6.sh"
sed -i 's#^x4: 8x1-ft1 (8X with the claim and defenders mixing too, 5ec36f1) against 8p-32-v41, seed 131.#x5: 8x2-ft1 (8X v2: the claim, and declarer and defenders mixing equal cards in proportion to p ** power, 2 and 3; 0bcdbc2) against 8p-32-v41, seed 131. x4: 8x1-ft1 (the same with uniform mixing, 5ec36f1; stopped).#' "$W/publish.sh"
grep -c "x5: 8x2" "$W/publish.sh"
cp "$S2/scripts/x8_forks.py" "$W/bin/x8_forks.py"
sudo systemctl restart x8-publish
sleep 120
systemctl is-active x8-queue4 x8-queue6 x8-publish; tail -3 "$W/queue.log"; tail -1 "$W/runs/x5.log" | cut -c1-160
ps -eo args | grep "[x]8_match.py" | grep -o "runs/[a-z0-9]*" | sort | uniq -c; uptime

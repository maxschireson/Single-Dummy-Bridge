# boxctl: timeout=600
# boxctl: timeout=600
# x8 session, azure6 (Max, 05:3x UTC): stop the 8Z leverage pair (z3, z5; partial records, resumable) and give its four workers
# to x6 = 8x3-ft1~8p-32-v41 (8X v3: Gen 8 through trick 6 with its tree, the blend from trick 7 in games only; 1a779a9), same
# deals (seed 131), from a third copy src3. x5 (8x2-ft1, src2 at 0bcdbc2) keeps running.
set -euo pipefail
COMMIT=1a779a9e67caef3d362015e621d0de18b5c6553c
W=$HOME/work/x8; S2=$W/src2; S3=$W/src3
sudo systemctl stop x8-queue4 2>/dev/null || true
pkill -f -- "--out $W/runs/z3" || true
pkill -f -- "--out $W/runs/z5" || true
sleep 4
sudo systemctl reset-failed x8-queue4 2>/dev/null || true
for z in z3 z5; do echo "$(date -u +%FT%TZ) $z stopped at $(wc -l < $W/runs/$z/results.jsonl) boards (8X v3 takes its workers, Max 05:3x)" >> "$W/queue.log"; done
rm -rf "$S3"; cp -a "$S2" "$S3"
git -C "$S3" fetch -q --depth 5 origin feature/gen8x-rollout-bot-20261113 && git -C "$S3" checkout -q "$COMMIT"
git -C "$S3" log -1 --format='src3 %h %s' | cut -c1-100
sed -e 's#S2=$W/src2#S2=$W/src3#' -e 's#x5 (8x2-ft1~8p-32-v41#x6 (8x3-ft1~8p-32-v41#' -e 's#--pair 8x2-ft1~8p-32-v41#--pair 8x3-ft1~8p-32-v41#' \
    -e 's#runs/x5#runs/x6#g' -e 's#end x5#end x6#' "$W/queue6.sh" > "$W/queue7.sh"
chmod +x "$W/queue7.sh"; grep -n "src3\|x6\|x5" "$W/queue7.sh"
sudo systemd-run --unit=x8-queue7 --uid="$USER" --working-directory="$W" --setenv=HOME="$HOME" -- "$W/queue7.sh"
sed -i "s#x5: 8x2-ft1 (8X v2#x6: 8x3-ft1 (8X v3: Gen 8 through trick 6 with its tree, the blend from trick 7 in games only, the claim, mixing as v2; 1a779a9) against 8p-32-v41, seed 131. z3, z5 stopped at 05:3x. x5: 8x2-ft1 (8X v2#" "$W/publish.sh"
grep -c "x6: 8x3" "$W/publish.sh" || true
sudo systemctl restart x8-publish
sleep 120
systemctl is-active x8-queue6 x8-queue7 x8-publish; tail -4 "$W/queue.log"; tail -1 "$W/runs/x6.log" | cut -c1-160
ps -eo args | grep "[x]8_match.py" | grep -o "runs/[a-z0-9]*" | sort | uniq -c; uptime

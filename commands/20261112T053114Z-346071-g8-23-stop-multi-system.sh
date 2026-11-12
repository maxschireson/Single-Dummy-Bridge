# boxctl: timeout=600
# boxctl: timeout=600
# g8: Max, 05:28 UTC: nothing made with the EPBot engine is to be part of Gen 8 or in the repository. Stop the
# multi-system match (its auctions were bid by that engine and its scorer was trained on such auctions), take it out of
# the queue, delete its results and the files it used from this box, and republish this box's results without it.
set -uo pipefail
G=$HOME/work/g8; BOX=$BOXCTL_BOX; BR=transfer/gen8-proto-$BOX-20261112
sudo systemctl stop g8-publish
pos=$(cat "$G/queue.pos")
{ head -n "$pos" "$G/queue.txt" | sed 's/^e4-.*/# (removed: multi-system match)/'; tail -n +$((pos + 1)) "$G/queue.txt" | grep -v '^e4-'; } > "$G/queue.new"
mv "$G/queue.new" "$G/queue.txt"
sudo systemctl restart g8-queue
rm -rf "$G/runs/e4-8y-v-8p" "$G/runs/e4-8y-v-8p.log" "$G/pub/e4-8y-v-8p" "$G/pub/e4-8y-v-8p.log"
for d in "$G/src" "$G/src-dry"; do
  rm -rf "$d/configs/gen8-books" "$d/models/cardplay/gen8-system-scorer-proto-v1-2026-11-12" "$d/bridge_harness/epbot_bidder.py" \
         "$d/configs/systems/epbot-precision.json" "$d/configs/systems/epbot-21gf.json" "$d/scripts/gen8_auction_book.py"
done
# this box's results branch becomes one snapshot without that match (its earlier publishes held it)
cd "$G/pub" || exit 1
export GIT_SSH_COMMAND="ssh -i $HOME/.ssh/boxctl_github -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new"
cp -f "$G/queue.txt" "$G/queue.pos" "$G/queue.log" . 2>/dev/null
sed -i 's/^.*e4-8y-v-8p.*$/(line removed)/' queue.log 2>/dev/null
git checkout -q --orphan clean-snapshot && git add -A && git -c user.name="g8 box publisher" -c user.email=noreply@anthropic.com commit -q \
  -m "Gen 8 prototype test results from $BOX, one snapshot ($(date -u +%FT%TZ))" \
  -m "Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxEA6NwcnXPZb3BY1s9" && git branch -M clean-snapshot "$BR" && git push -q --force origin "$BR" 2>&1 | tail -1
echo "results branch: $(git log --oneline | wc -l) commit(s); folders: $(ls -d */ | tr '\n' ' ')"
sudo systemd-run --quiet --unit=g8-publish --uid="$(id -un)" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 \
  --working-directory="$G" -- "$G/pub.sh" "$BOX" 2>&1 | tail -1
sleep 20
echo "queue position $(cat "$G/queue.pos"):"; cat -n "$G/queue.txt" | tail -6 | cut -c1-110; tail -2 "$G/queue.log" | cut -c1-150
echo "publisher: $(systemctl is-active g8-publish); queue: $(systemctl is-active g8-queue)"
ls "$G/runs" | grep -c e4; grep -rl "epbot" "$G/src/configs" "$G/src/bridge_harness" 2>/dev/null | head -5

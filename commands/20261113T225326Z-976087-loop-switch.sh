# boxctl: timeout=1800
# boxctl: timeout=1800
# loop session: round 3's cut on this box and the switch to pure rollout (Max, 22:19 UTC: "My instinct is to just go pure
# rollout"). The two collection runs stop; the chain restarts on 1a40de0 with all eight workers on pure Stu with the lead
# rolled out on the settings of every other card (stu0-psa~stu0-psb), workers recycled every 20 boards (eight workers
# now, so a lower peak); the row publisher moves to the new run; then the stopped runs' boards past their last block are
# built once (rows_cut.sh) for round 3.
set -euo pipefail
COMMIT=1a40de0ca034c886228480e0d834550c7a2d19d2
W=$HOME/work/loop; S=$W/src; T=$S/training/rollout-loop-20261113
B=$(cat "$W/pub/.git/HEAD" 2>/dev/null | sed 's#.*rollout-loop-\(azure[0-9]\)-.*#\1#')
case "$B" in azure3) OLD="sp0b spr0b"; NEW=sps0b ;; azure6) OLD="sp0c spr0c"; NEW=sps0c ;; azure2) OLD="sp0d spr0d"; NEW=sps0d ;;
             azure1) OLD="sp0e spr0e"; NEW=sps0e ;; *) echo "not a box for this script: $B"; exit 1 ;; esac
U=loop-collect; [ "$B" = azure3 ] && U=loop-chain
sudo systemctl stop "$U" loop-collect-b loop-rows 2>/dev/null || true
echo "$(date -u +%FT%TZ) round 3's cut: $OLD stopped; the collection moves to $NEW (pure rollout)" >> "$W/runs.log"
git -C "$S" fetch -q --depth 8 origin research/rollout-loop-20261113 && git -C "$S" diff --stat HEAD "$COMMIT" -- bridge_harness scripts | tail -2
git -C "$S" checkout -q "$COMMIT"; git -C "$S" log -1 --format='source %h'
echo 20 > "$W/RECYCLE"
sudo systemctl reset-failed "$U" loop-collect-b loop-rows 2>/dev/null || true
sudo systemd-run --unit="$U" --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=30 -- bash "$T/chain.sh" "$T/jobs-$B.txt"
sudo systemd-run --unit=loop-rows --uid="$USER" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/rows.sh" "$NEW"
sleep 20; echo "box $B: $(systemctl is-active "$U" loop-rows loop-publish | tr '\n' ' ')"; tail -n 2 "$W/runs.log" | cut -c1-220
cd "$S"; bash "$T/rows_cut.sh" $OLD
for r in $OLD; do echo "$r $(wc -l < "$W/runs/$r/results.jsonl") tables (final)"; done
free -m | sed -n 2p; date -u +%FT%TZ

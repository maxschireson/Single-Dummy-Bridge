# boxctl: timeout=60
# azure1 (Max, 15:46 UTC: "Let's wrap this up"): stop the settings matches, push their results, return to the 7.1 mix (gen71-mix2-azure1).
# Background unit wrap1; progress in ~/work/settings/wrap1.log.
set -euo pipefail
X=$HOME/work/settings
[ "$BOXCTL_BOX" = azure1 ] || { echo "this command is for azure1"; exit 1; }
cat > "$X/wrap1.sh" <<'EOF_WRAP'
#!/usr/bin/env bash
# azure1: end the settings matches (Max, 15:46 UTC: "Let's wrap this up"), push their results a last time, and return the box to
# Max's 7.1 self-play and 7.1 against 7.0 mix with the prepared cohort gen71-mix2-azure1 (capture-capsule shard 5/8).
set -uo pipefail
W=$HOME/work; S=$W/gen71; X=$W/settings
say() { echo "$(date -u +%T) $*"; }
sudo systemctl stop match-m1 match-m3
say "matches stopped: m1 $(wc -l < $X/m1/results.jsonl) boards, m3 $(wc -l < $X/m3/results.jsonl) boards"
sudo systemctl stop settings-pub
P=$X/publication
for m in m1 m3; do mkdir -p "$P/$m"; cp "$X/$m/results.jsonl" "$P/$m/"; [ -e "$X/$m/summary.json" ] && cp "$X/$m/summary.json" "$P/$m/"; done
cp "$X/bots.json" "$X/README.md" "$P/" 2>/dev/null
cat > "$P/FINDINGS.md" <<'MDEOF'
# Findings (15:47 UTC, 12 November 2026)

Stopped at Max's word after 1,081 boards each (seed 7111, deals 0 on, the same deals in both matches; common bidding).

| Match | IMPs a board for the first bot |
|---|---|
| `m1`: `71s-32-w1` (7.1, layout-weight exponent 1.0) against `7s-32` (7.0 as deployed, 0.5) | +0.137 +- 0.079 |
| `m3`: `71s-32-w1` against `7s-32-w1` (7.0 at 1.0) | +0.111 +- 0.078 |
| `m1` minus `m3`, board by board on the same deals: 7.0 at 1.0 over 7.0 at 0.5 | +0.026 +- 0.038 |

1,040 of the 1,081 boards came out the same in both matches (correlation 0.88): moving 7.0's exponent from 0.5 to 1.0
changed the result on 41 boards. The exponent barely changes the Gen 7 bot's play, as the 4.1 session's bench predicted
(the Gen 7 bot reads the play only from the deal list on, where 1.0 over 0.5 is worth +0.004 to +0.008 tricks a board).
So both matches are, in effect, 7.1 against 7.0 again, fork-free on random deals.
MDEOF
git -C "$P" add -A >/dev/null 2>&1
git -C "$P" commit -q -m "Gen 7.1 settings matches on azure1: final, stopped at Max's word (15:46 UTC)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01N2EvxEiuqLC6xtt2hftSWZ" 2>/dev/null
git -C "$P" push -q -f origin HEAD:refs/heads/transfer/gen71-settings-azure1-20261112 && say "results pushed: $(git -C "$P" rev-parse --short HEAD)" || say "push FAILED"
say "== the 7.1 mix, next cohort"
[ "$(systemctl is-active arena-gen71)" = active ] && { say "a collector is already running; stopping here"; exit 1; }
bash "$S/gen71e.sh" units && bash "$S/gen71e.sh" start 8 || { say "start FAILED"; exit 1; }
rm -f "$S/RECYCLE_OFF" "$S/SWITCH_OFF"
sudo systemctl enable --now gen71-recycle >/dev/null 2>&1
say "collector $(systemctl is-active arena-gen71) on $(systemctl show -p ExecStart --value arena-gen71 | sed -n 's/.*--run \([^ ;]*\).*/\1/p' | head -1 | xargs basename); publisher $(systemctl is-active arena-gen71-publish); gen71-recycle $(systemctl is-active gen71-recycle); cache $(readlink $W/runs/gen71-mix2-azure1/dds-cache.sqlite)"
say DONE
EOF_WRAP
chmod +x "$X/wrap1.sh"
sudo systemctl reset-failed wrap1 2>/dev/null || true
sudo systemd-run --quiet --unit=wrap1 --uid="$(id -un)" --setenv=HOME="$HOME" \
  --property=StandardOutput=append:"$X/wrap1.log" --property=StandardError=append:"$X/wrap1.log" -- "$X/wrap1.sh"
sleep 30; echo "wrap1: $(systemctl is-active wrap1)"; tail -7 "$X/wrap1.log" | cut -c1-260

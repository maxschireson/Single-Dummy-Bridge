# boxctl: timeout=600
# boxctl: timeout=600
# loop session (Max, 08:23 UTC 13 Nov: "Take azure 3 and 5"; board entry 08:32): drain azure3's eight BEN lanes as g7's own
# ~/work/lanes/drain71.sh does, for the runs the lanes are on now. Collectors stop after the board in hand (STOP), every
# feed is waited for (publisher-status == receipts), then the publishers stop (PUBLISH_STOP). Nothing is deleted, no unit is
# disabled, the BEN servers stay up. Lane 6 (13 boards from the end of its second pool at 08:37) is given until 09:00 to
# finish. Runs as unit loop-drain; log ~/work/loop/drain.log.
# To resume a lane later: rm $RUN/STOP $RUN/PUBLISH_STOP; sudo systemctl start arena-ben@N arena-ben-publish@N
# (and rm ~/work/lanes/SWITCH_OFF ~/work/lanes/RECYCLE_OFF for the switcher and the memory supervisor).
set -uo pipefail
mkdir -p "$HOME/work/loop"
cat > "$HOME/work/loop/drain.sh" <<'SH'
#!/usr/bin/env bash
set -uo pipefail
W=$HOME/work; L=$W/lanes; PY=$W/venv/bin/python
say() { echo "$(date -u +%FT%TZ) $*"; }
run() { (. "$L/$1.env"; echo "$RUN"); }
active() { [ "$(systemctl is-active "$1")" = active ]; }
echo "loop session, $(date -u +%FT%TZ): Max assigned azure3 to the loop at 08:23 UTC (board, 08:32 entry). Remove to let lanes recycle again." > "$L/RECYCLE_OFF"
for i in $(seq 1 120); do ls "$L"/*.recycling >/dev/null 2>&1 || break; sleep 5; done
say "RECYCLE_OFF and SWITCH_OFF in place; stopping lanes 1 2 3 4 5 7 8 after the board in hand"
for n in 1 2 3 4 5 7 8; do touch "$(run $n)/STOP"; say "lane $n: STOP in $(basename "$(run $n)") at $(ls "$(run $n)/receipts" | wc -l) boards"; done
a=7
for i in $(seq 1 240); do a=0; for n in 1 2 3 4 5 7 8; do active "arena-ben@$n" && a=$((a+1)); done; [ "$a" -eq 0 ] && break; sleep 5; done
if [ "$a" -ne 0 ]; then say "collectors still running after 20 minutes: $a; left as they are, publishers not stopped"; exit 1; fi
say "lanes 1 2 3 4 5 7 8: collectors stopped; starting the loop's job chain and publisher"
ME=$(id -un); S=$HOME/work/loop/src; T=$S/training/rollout-loop-20261113
sudo systemctl reset-failed loop-chain loop-publish 2>/dev/null || true
sudo systemd-run --unit=loop-chain --uid="$ME" --working-directory="$S" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/chain.sh" "$HOME/work/loop/jobs.txt"
sudo systemd-run --unit=loop-publish --uid="$ME" --working-directory="$HOME/work/loop" --setenv=HOME="$HOME" --property=Restart=on-failure --property=RestartSec=60 -- bash "$T/pub.sh" azure3
# lane 6: until 09:00 UTC to finish its second pool
LIMIT=$(date -u -d '2026-11-13 09:00:00' +%s)
while active arena-ben@6 && [ "$(date -u +%s)" -lt "$LIMIT" ]; do sleep 10; done
if active arena-ben@6; then touch "$(run 6)/STOP"; say "lane 6: STOP in $(basename "$(run 6)") at $(ls "$(run 6)/receipts" | wc -l) boards (09:00 reached)"; else say "lane 6: collector ended by itself at $(ls "$(run 6)/receipts" | wc -l) boards"; fi
for i in $(seq 1 240); do active arena-ben@6 || break; sleep 5; done
if active arena-ben@6; then say "lane 6: collector still running after 20 minutes; left as it is, publishers not stopped"; exit 1; fi
say "all eight collectors have stopped"
for n in 1 2 3 4 5 6 7 8; do f=$(ls "$(run $n)/failures" 2>/dev/null | tr '\n' ' '); [ -z "$f" ] || say "lane $n has a failure record: $f"; done
behind=8
for i in $(seq 1 90); do
  behind=0
  for n in 1 2 3 4 5 6 7 8; do
    p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$(run $n)/publisher-status.json" 2>/dev/null); r=$(ls "$(run $n)/receipts" | wc -l)
    [ "$p" = "$r" ] || behind=$((behind+1))
  done
  [ "$behind" -eq 0 ] && break; sleep 10
done
if [ "$behind" -ne 0 ]; then say "feeds still behind after 15 minutes: $behind; publishers left running"; exit 1; fi
for n in 1 2 3 4 5 6 7 8; do touch "$(run $n)/PUBLISH_STOP"; done
for i in $(seq 1 36); do a=0; for n in 1 2 3 4 5 6 7 8; do active "arena-ben-publish@$n" && a=$((a+1)); done; [ "$a" -eq 0 ] && break; sleep 5; done
for n in 1 2 3 4 5 6 7 8; do sudo systemctl stop "arena-ben-publish@$n" >/dev/null 2>&1; done
total=0
for n in 1 2 3 4 5 6 7 8; do R=$(run $n); k=$(ls "$R/receipts" | wc -l); total=$((total + k)); P=$(. "$L/$n.env"; echo "$PUB")
  say "lane $n: $(basename "$R") $k boards, all published, feed head $(git -C "$P" rev-parse --short HEAD 2>/dev/null)"; done
say "DRAINED: eight lanes stopped at a board boundary, $total boards in their current runs, every one published; BEN servers left up"
SH
chmod +x "$HOME/work/loop/drain.sh"
cat > "$HOME/work/loop/jobs.txt" <<'JOBS'
# azure3, loop round 0. NAME PAIR SEED FIRST DEALS WORKERS [options]; each job resumes.
# The gate's baseline: round 0's bot against Gen 8 card play on the gate's deals.
g0-v2 z0a-v2~8p-32-v41 131 0 2000 8
# The leverage control at ten times the sandbox's deals.
c-n41-n4 n-v41~n-v4 131 0 3000 8
c-r7-n41 r7-v41~n-v41 131 0 3000 8
c-r7x4-n41 r7x-v4~n-v41 131 0 3000 8
c-r7-n4 r7-v41~n-v4 131 0 3000 8
c-r7x4-n4 r7x-v4~n-v4 131 0 3000 8
c-r7-r7f4 r7-v41~r7f-v4 131 0 3000 8
# Round 0's collection, second shard of the deals (azure5 plays 0 to 19,999).
r0b z0a-v2~z0b-v2 9001 20000 20000 8 --episodes
JOBS
sudo systemctl reset-failed loop-drain 2>/dev/null || true
sudo systemd-run --unit=loop-drain --uid="$USER" --working-directory="$HOME/work/loop" --setenv=HOME="$HOME" --property=StandardOutput=append:"$HOME/work/loop/drain.log" --property=StandardError=append:"$HOME/work/loop/drain.log" -- bash "$HOME/work/loop/drain.sh"
sleep 8; cat "$HOME/work/loop/drain.log"; systemctl is-active loop-drain

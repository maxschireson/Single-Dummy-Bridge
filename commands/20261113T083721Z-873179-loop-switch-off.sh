# loop session (Max, 08:23 UTC 13 Nov: "Take azure 3 and 5"): keep the lanes that are ending their second pools from moving
# to the fresh pools, with lane-switch's own documented switch. Nothing is stopped by this. Undo: rm ~/work/lanes/SWITCH_OFF
L=$HOME/work/lanes
echo "loop session, $(date -u +%FT%TZ): Max assigned azure3 to the loop at 08:23 UTC (board, 08:32 entry). Remove to let lanes switch again." > "$L/SWITCH_OFF"
ls -la "$L/SWITCH_OFF"; tail -n 3 "$L/laneswitch.log" | cut -c1-200
PY=$HOME/work/venv/bin/python
for n in 1 2 3 4 5 6 7 8; do R=$(. "$L/$n.env"; echo "$RUN"); t=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1]))['target'])" "$R/manifest.json"); k=$(ls "$R/receipts" | wc -l); p=$("$PY" -c "import json,sys; print(json.load(open(sys.argv[1])).get('completed'))" "$R/publisher-status.json" 2>/dev/null); echo "lane $n: $(basename "$R") $k of $t played, $p published; collector $(systemctl is-active arena-ben@$n), next: $([ -e "$L/$n.next.env" ] && (. "$L/$n.next.env"; basename "$RUN") || echo none)"; done
date -u +%FT%TZ

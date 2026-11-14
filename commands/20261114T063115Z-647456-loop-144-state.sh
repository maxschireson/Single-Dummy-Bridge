# boxctl: timeout=60
# boxctl: timeout=60
# loop session (read-only): roles, units and the newest runs on this box.
W=$HOME/work/loop
grep -E "role from here|joins the gate|has ended|start (sg8|sp3t|s8-|bu3)|not played|did not pass" "$W/runs.log" | tail -n 5 | cut -c1-170
echo "units: $(for u in loop-collect loop-chain loop-collect-b loop-rungs loop-rungs2 loop-rungs3 loop-next loop-bensession loop-switch loop-rows; do [ "$(systemctl is-active $u 2>/dev/null)" = active ] && printf '%s ' $u; done)"
echo "source $(git -C $W/src log -1 --format=%h) | rows unit: $(systemctl show -p ExecStart loop-rows 2>/dev/null | grep -o 'rows.sh[^;]*' | cut -c1-150)"
for r in sg8s1 sg8t1 sp3t sp3tb s8-greedy; do [ -e $W/runs/$r/results.jsonl ] && echo "$r $(wc -l < $W/runs/$r/results.jsonl) tables"; done

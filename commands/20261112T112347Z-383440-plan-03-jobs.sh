# boxctl: timeout=180
# boxctl: timeout=180
# plan session: first jobs for the queue under ~/work/plan (azure2 is plan's since 08:15 UTC; BOARD.md, g7's 08:16 entry).
set -uo pipefail
P=$HOME/work/plan
for u in arena-gen71 arena-gen71-publish gen71-recycle; do systemctl is-active --quiet $u && { echo "$u is active: not queuing anything"; exit 1; }; done
echo "before: $(uptime | sed 's/.*load/load/'); arena python processes: $(pgrep -fc 'gen5_arena|run_arena|ben' || true)"
cat >> "$P/queue.txt" <<'Q'
@source 94418bdc092bcfd7f97df15d46c5a2002fbc6933
net1 $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v41:top;v41:blend;v41:draw:4;v41:top:1:2;v41:top:1:3;v4:top;v4:blend;v4:top:1:3;v2:top;v0:top" --from-trick 3 --to-trick 6 --workers 8 --out $R.json
bel1a $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v41:top;v41:map;v41:hyb;v41:hyb3;v41:own4" --from-trick 3 --to-trick 6 --files 800 --workers 8 --out $R.json
ceil16a $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --files 500 --workers 8 --out $R.json
matrix1 $PY scripts/plan_matrix_study.py --episodes $P/data/fresh_g6sp --net models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --decisions 800 --own-layouts 4 --workers 8 --out $R.json
bel1b $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v0:hyb3;v2:hyb3;v4:hyb3;v0:map;v4:map;v41:map3" --from-trick 3 --to-trick 6 --files 800 --workers 8 --out $R.json
ceil16b $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --skip-files 500 --workers 8 --out $R.json
fam1 $PY scripts/plan_family_study.py --episodes $P/data/fresh_g6sp --net models/cardplay/gen7-policy-v4.1-2026-11-12/gen7_policy_v4.1.npz --layouts 128 --decisions 2000 --workers 8 --out $R.json
Q
sleep 45
echo "queue: $(systemctl is-active plan-queue); publisher: $(systemctl is-active plan-publish); jobs listed: $(wc -l < "$P/queue.txt"); position $(cat "$P/queue.pos")"
tail -4 "$P/queue.log" 2>/dev/null | cut -c1-220
tail -2 "$P/runs/net1.log" 2>/dev/null | cut -c1-200
uptime | sed 's/.*load/load/'

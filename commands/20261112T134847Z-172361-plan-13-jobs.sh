# boxctl: timeout=300
# boxctl: timeout=120
# plan session: jobs for azure5 (lent by g8, 13:20 UTC): ceilings at other tricks and more deals, and hybrid seats with more believed layouts.
set -uo pipefail
P=$HOME/work/plan
cat >> "$P/queue.txt" <<'Q'
ceilT712b $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 32 --from-trick 7 --to-trick 12 --skip-files 500 --workers 8 --out $R.json
ceilT12 $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --from-trick 1 --to-trick 2 --files 400 --workers 8 --out $R.json
wide3 $PY scripts/plan_bench.py --episodes $P/data/fresh_g6sp --nets $NETS --sims "v41:hyb5;v41:hyb8" --from-trick 3 --to-trick 6 --files 500 --seed 1 --layouts 128 --max-gap 0.25 --workers 8 --out $R.json
ceil16c $PY scripts/plan_ceiling.py --episodes $P/data/fresh_g6sp --worlds 16 --skip-files 1000 --workers 8 --out $R.json
Q
sleep 20
echo "queue: $(systemctl is-active plan-queue); publisher: $(systemctl is-active plan-publish); jobs listed: $(wc -l < "$P/queue.txt"); position $(cat "$P/queue.pos")"; tail -2 "$P/queue.log" | cut -c1-120

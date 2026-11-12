# boxctl: timeout=1200
# Final figures for the 7s-32 vs 6-32 box test: rate after the restart, score, tree use and cost.
RUN=$HOME/work/runs/g7s-vs-g6f-01
cd "$HOME/work/sdb-gen7"
echo "unit: $(systemctl is-active g7s-vs-g6f-01b)"
"$HOME/work/venv/bin/python" - "$RUN" <<'PY'
import glob, json, math, sys
run = sys.argv[1]
rs = sorted((json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')), key=lambda r: r['completed_epoch'])
restart = 1794447856  # 2026-11-12T01:44:16Z, collector restarted with one thread per worker
after = [r for r in rs if r['completed_epoch'] > restart + 60]
span = after[-1]['completed_epoch'] - after[0]['completed_epoch']
print(f"boards {len(rs)}; after the restart's first minute {len(after)} boards in {span:.0f}s = {3600 * (len(after) - 1) / span:.0f} an hour on 8 workers")
def ms(x):
    n = len(x); mu = sum(x) / n; return mu, math.sqrt(sum((v - mu) ** 2 for v in x) / (n - 1) / n)
c = [r['imps'] for r in rs]
print("common: %+.3f +- %.3f IMPs a board" % ms(c), f"(wins {sum(v > 0 for v in c)}, flat {sum(v == 0 for v in c)}, losses {sum(v < 0 for v in c)}); native: %+.3f +- %.3f" % ms([r['own_imps'] for r in rs]))
print(f"root games {sum(r['root_games'] for r in rs)}, tables {sum(r['tables'] for r in rs)}, tables a board {sum(r['tables'] for r in rs) / len(rs):.1f}")
idx = sorted(r['index'] for r in rs); print(f"deal indices {idx[0]}..{idx[-1]}, contiguous to {next(i for i in range(len(idx) + 1) if i not in set(idx))}")
PY
echo "== failures: $(ls "$RUN/failures" | wc -l)"
echo "== gen7_alpha_report"
"$HOME/work/venv/bin/python" scripts/gen7_alpha_report.py --episodes "$RUN/episodes" --out "$HOME/work/runs/report-01.json" 2>&1 | tail -60 | cut -c1-220
echo "== board cost"
timeout 600 "$HOME/work/venv/bin/python" scripts/gen7_board_cost.py "$RUN/episodes" 2>&1 | tail -30 | cut -c1-220

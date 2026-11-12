# boxctl: timeout=180
# Progress of the 7s-32 vs 6-32 match: boards, rate, interim IMPs, load.
RUN=$HOME/work/runs/g7s-vs-g6f-01
echo "unit: $(systemctl is-active g7s-vs-g6f-01b)"; uptime
journalctl -u g7s-vs-g6f-01b --no-pager -n 3 -o cat
"$HOME/work/venv/bin/python" - "$RUN" <<'PY'
import glob, json, math, os, sys
run = sys.argv[1]
rs = [json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')]
if not rs:
    print('no boards yet'); sys.exit()
rs.sort(key=lambda r: r['completed_epoch'])
m = json.load(open(run + '/manifest.json'))
t0 = m['created_epoch']
start = min(r['completed_epoch'] for r in rs)
span = rs[-1]['completed_epoch'] - start
rate = (len(rs) - 1) / span * 3600 if span > 0 else float('nan')
def ms(x):
    n = len(x); mu = sum(x) / n
    se = math.sqrt(sum((v - mu) ** 2 for v in x) / (n - 1) / n) if n > 1 else float('nan')
    return mu, se
c = [r['imps'] for r in rs]; o = [r['own_imps'] for r in rs]
print(f"boards {len(rs)}, {rate:.0f} an hour since the first finished; root games {sum(r['root_games'] for r in rs)}, tables {sum(r['tables'] for r in rs)}")
print("common auctions: %+.3f +- %.3f IMPs a board" % ms(c), f"(wins {sum(v > 0 for v in c)}, flat {sum(v == 0 for v in c)}, losses {sum(v < 0 for v in c)})")
print("native auctions: %+.3f +- %.3f IMPs a board" % ms(o))
print('pairs:', {p: sum(r['pair'] == p for r in rs) for p in {r['pair'] for r in rs}})
PY
ls "$RUN/failures" 2>/dev/null | head -3
tail -2 "$RUN.collector.log" 2>/dev/null | cut -c1-200

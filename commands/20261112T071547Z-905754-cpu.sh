# boxctl: timeout=120
# Read-only: where a board's CPU goes (base play, audit forks, gap forks) on this box's current Gen 7.1 runs, and wall time.
set -uo pipefail
W=$HOME/work
"$W/venv/bin/python" - "$W" <<'PY'
import glob, gzip, json, os, sys, time
w = sys.argv[1]
runs = sorted(glob.glob(w + '/runs/gen71-vs70-fresh-*') + glob.glob(w + '/runs/gen71fresh-*') + glob.glob(w + '/runs/gen7-phase1-azure[1-4]') + glob.glob(w + '/runs/gen71-vs70-azure2'))
for run in runs:
    rs = sorted((json.load(open(p)) for p in glob.glob(run + '/receipts/*.json')), key=lambda r: r['completed_epoch'])
    if not rs: continue
    by = {}
    for r in rs[-120:]:
        p = f"{run}/episodes/{r['index']:06d}.json.gz"
        try: d = json.load(gzip.open(p, 'rt'))
        except Exception: continue
        b = by.setdefault(r['pair'], dict(n=0, base=0, branch=0, gap=0, forks=0, gaps=0))
        b['n'] += 1; b['base'] += d.get('base_cpu', 0); b['branch'] += d.get('branch_cpu', 0); b['gap'] += d.get('gap_cpu', 0)
        b['forks'] += sum(len(e.get('audits', [])) for e in d['unique_tables'].values()); b['gaps'] += d.get('gap_fork_count', 0)
    span = (rs[-1]['completed_epoch'] - rs[max(0, len(rs) - 120)]['completed_epoch']) / 3600
    print(f"{os.path.basename(run)}: {len(rs)} boards; last {min(120, len(rs))} at {round((min(120, len(rs)) - 1) / span) if span else '?'}/h")
    for pair, b in by.items():
        n = b['n']; tot = b['base'] + b['branch'] + b['gap']
        print(f"   {pair}: {n} boards, cpu-s a board {tot / n:.0f} = base {b['base'] / n:.0f} ({100 * b['base'] / tot:.0f}%) + audit forks {b['branch'] / n:.0f} ({100 * b['branch'] / tot:.0f}%) + gap forks {b['gap'] / n:.0f} ({100 * b['gap'] / tot:.0f}%); audit forks {b['forks'] / n:.1f}, gap forks {b['gaps'] / n:.1f} a board")
PY

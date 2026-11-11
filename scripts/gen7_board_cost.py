#!/usr/bin/env python3
"""Where a board's compute goes: cpu-seconds and decisions by stage of play, at root tables and at fork tables
(only the part of a fork table after its fork), by player.  python scripts/gen7_board_cost.py EPISODES_DIR [MAX_FILES]"""
import collections, glob, gzip, json, random, sys
STAGES = ('lead', 'tricks 1-2', 'tricks 3-6', 'tricks 7-13')
stage = lambda ply: 0 if ply == 0 else 1 if ply < 8 else 2 if ply < 24 else 3
files = sorted(glob.glob(sys.argv[1] + '/*.json.gz'))
if len(sys.argv) > 2 and len(files) > int(sys.argv[2]):
    random.seed(0); files = random.sample(files, int(sys.argv[2]))
cpu = collections.defaultdict(float); n = collections.defaultdict(int)
boards = roots = forks = 0; own = recorded = 0.
totals = collections.defaultdict(float)
for f in files:
    d = json.load(gzip.open(f)); boards += 1
    for k in ('base_cpu', 'branch_cpu', 'gap_cpu'):
        totals[k] += d.get(k, 0.)
    names = {'candidate': str(d.get('candidate')), 'opponent': str(d.get('opponent'))}
    for tb in d['unique_tables'].values():
        for t in tb['tables']:
            node = str(t.get('node', 'root'))
            nums = [int(x) for x in node.split('/') if x.isdigit()]
            fork = nums[-1] if nums else -1
            kind = 'root' if fork < 0 else 'gap fork' if '/gap/' in node else 'tie fork'
            roots += fork < 0; forks += fork >= 0
            if fork >= 0: recorded += t.get('cpu_seconds', 0.)
            for a in t['actions']:
                if a['ply'] <= fork: continue
                who = names.get(a['player'], a['player'])
                cpu[(kind, who, stage(a['ply']))] += a.get('cpu_seconds', 0.); n[(kind, who, stage(a['ply']))] += 1
                if fork >= 0: own += a.get('cpu_seconds', 0.)
print(f"{sys.argv[1]}: boards {boards}, root tables {roots}, fork tables {forks}; per board: " + ', '.join(f"{k} {v / boards:.2f}" for k, v in totals.items()))
print(f"fork tables' own cpu per board: recorded {recorded / boards:.2f}, summed from decisions after the fork {own / boards:.2f}")
for kind in ('root', 'tie fork', 'gap fork'):
    for who in sorted({k[1] for k in cpu if k[0] == kind}):
        row = [(cpu[(kind, who, s)] / boards, n[(kind, who, s)] / boards) for s in range(4)]
        print(f"  {kind} {who:10s} cpu-s per board {sum(r[0] for r in row):6.2f} | " + ' | '.join(f"{STAGES[s]}: {row[s][0]:.2f} s, {row[s][1]:.1f} dec, {1000 * row[s][0] / max(row[s][1], 1e-9):.0f} ms each" for s in range(4)))

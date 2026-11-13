"""Leverage check: the same rollout bot from trick 7, with different nets as its simulated seats, against v4.1 alone."""
import json, os
def load(name):
    p = f'/home/claude/work/smoke/{name}/results.jsonl'
    if not os.path.exists(p): return {}
    return {json.loads(l)['index']: json.loads(l) for l in open(p) if l.strip()}
def stat(v):
    n = len(v)
    if n < 2: return float('nan'), float('nan'), n
    m = sum(v) / n; sd = (sum((x - m) ** 2 for x in v) / (n - 1)) ** .5
    return m, sd / n ** .5, n
arms = {'v0': load('r7x_v0'), 'v4': load('r7x_v4'), 'v4.1': load('r7')}
for k, d in arms.items():
    if not d: continue
    v = [r['common'] for r in d.values()]
    m, se, n = stat(v)
    x = [r['search']['candidate']['x8'] for r in d.values()]
    dec = sum(a['rollout'] for a in x); mv = sum(a['moved'] for a in x)
    print(f'rollouts on {k:5} vs v4.1 alone: {m:+.2f} +- {se:.2f} IMPs a board over {n} (won {sum(a > 0 for a in v)}, lost {sum(a < 0 for a in v)}, flat {sum(a == 0 for a in v)}); moved {mv / max(dec, 1):.1%} of {dec / max(n, 1):.1f} decisions a board')
for a, b in (('v4', 'v0'), ('v4.1', 'v4'), ('v4.1', 'v0')):
    A, B = arms[a], arms[b]
    both = sorted(set(A) & set(B))
    if len(both) < 2: continue
    m, se, n = stat([A[i]['common'] - B[i]['common'] for i in both])
    print(f'paired by deal, rollouts on {a} minus rollouts on {b}: {m:+.2f} +- {se:.2f} IMPs a board over {n}')

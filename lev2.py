"""Control for the leverage check: split 'better net inside the rollouts' from 'exact model of the opponent'.

Rows: the rollout bot from trick 7 with v4.1 or v4 as its simulated seats (table net and prior v4.1 in both).
Columns: the opponent, v4.1 alone or v4 alone. Same 300 deals (seed 131) in every match, so everything is paired by deal.
"""
import json, os


def load(name):
    p = f'/home/claude/work/smoke/{name}/results.jsonl'
    if not os.path.exists(p):
        return {}
    return {json.loads(l)['index']: json.loads(l) for l in open(p) if l.strip()}


def stat(v):
    n = len(v)
    if n < 2:
        return float('nan'), float('nan'), n
    m = sum(v) / n
    sd = (sum((x - m) ** 2 for x in v) / (n - 1)) ** .5
    return m, sd / n ** .5, n


def line(label, v):
    m, se, n = stat(v)
    print(f'{label}: {m:+.2f} +- {se:.2f} over {n} (won {sum(a > 0 for a in v)}, lost {sum(a < 0 for a in v)}, flat {sum(a == 0 for a in v)})')


M = {
    'R41|N41': load('r7'), 'R4|N41': load('r7x_v4'), 'R0|N41': load('r7x_v0'),
    'N41|N4': load('c_n41_n4'), 'R41|N4': load('c_r7_n4'), 'R4|N4': load('c_r7x4_n4'),
    'F41|F4': load('c_r7_r7f4'),
}
names = {
    'R41|N41': 'rollouts on v4.1 vs v4.1 alone', 'R4|N41': 'rollouts on v4   vs v4.1 alone', 'R0|N41': 'rollouts on v0   vs v4.1 alone',
    'N41|N4': 'v4.1 alone       vs v4 alone  ', 'R41|N4': 'rollouts on v4.1 vs v4 alone  ', 'R4|N4': 'rollouts on v4   vs v4 alone  ',
    'F41|F4': 'rollout bot all v4.1 vs rollout bot all v4',
}
for k, d in M.items():
    if d:
        line(names[k], [r['common'] for r in d.values()])


def paired(a, b, label):
    A, B = M[a], M[b]
    both = sorted(set(A) & set(B))
    if len(both) < 2:
        return None
    v = [A[i]['common'] - B[i]['common'] for i in both]
    m, se, n = stat(v)
    print(f'paired: {label}: {m:+.2f} +- {se:.2f} over {n}')
    return dict(zip(both, v))


print()
g1 = paired('R41|N41', 'R4|N41', 'opponent v4.1 alone, v4.1 inside minus v4 inside (better net AND exact model)')
g2 = paired('R41|N4', 'R4|N4', 'opponent v4 alone,   v4.1 inside minus v4 inside (better net, v4 is the exact model)')
paired('R41|N4', 'N41|N4', 'opponent v4 alone, rollouts on v4.1 minus v4.1 alone (what rollouts add, inexact model)')
paired('R4|N4', 'N41|N4', 'opponent v4 alone, rollouts on v4   minus v4.1 alone (what rollouts add, exact model)')
if g1 and g2:
    both = sorted(set(g1) & set(g2))
    if len(both) > 1:
        m, se, n = stat([(g1[i] + g2[i]) / 2 for i in both])
        print(f'net quality (half the sum of the two gaps): {m:+.2f} +- {se:.2f} over {n}')
        m, se, n = stat([(g1[i] - g2[i]) / 2 for i in both])
        print(f'exact model (half the difference):          {m:+.2f} +- {se:.2f} over {n}')
paired('F41|F4', 'N41|N4', 'generation gap with rollouts minus generation gap of the nets alone')

for k in ('R41|N4', 'R4|N4', 'F41|F4'):
    d = M[k]
    if not d:
        continue
    for role in ('candidate', 'opponent'):
        x = [r['search'][role].get('x8') for r in d.values() if r.get('search', {}).get(role)]
        x = [a for a in x if a and a.get('rollout')]
        if x:
            dec = sum(a['rollout'] for a in x)
            mv = sum(a['moved'] for a in x)
            print(f'{names[k].strip()} [{role}]: moved {mv / max(dec, 1):.1%} of {dec / len(x):.1f} rollout decisions a board')

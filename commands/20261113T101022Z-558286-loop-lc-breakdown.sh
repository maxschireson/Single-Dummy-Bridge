# loop session: the learning-curve runs' scores split by side and phase of play (read-only)
"$HOME/work/loop/venv/bin/python" - <<'PY'
import json, os
L = os.path.expanduser('~/work/loop/lc')
def show(tag, v):
    parts = []
    for k in ('declaring', 'defending'):
        parts.append('%s nll %.3f agree %.3f n %d' % (k, v[k]['nll'], v[k]['agree'], v[k]['n']))
    for k, s in v['by_phase'].items():
        parts.append('%s nll %.3f agree %.3f' % (k, s['nll'], s['agree']))
    print(tag, '|', ' | '.join(parts))
b = json.load(open(L + '/run-base/metrics.json')); f1 = json.load(open(L + '/run-f1/metrics.json'))
show('v2 as 8s-32 ', b['validation']); show('523 boards  ', f1['validation'])
for k, v in b['compared'].items():
    show(os.path.basename(k)[:12], v)
print('epochs of the 523-board run:', [(h['epoch'], h['val']['nll'], h['val']['agree'], h['val']['regret']) for h in f1['history']])
a0, a1 = b['validation']['all'], f1['validation']['all']
print('all rows: in_best', a0['in_best'], a1['in_best'], '| regret', a0['regret'], a1['regret'], '| regret_gap_head', a0['regret_gap_head'], a1['regret_gap_head'], '| regret_random', a1['regret_random'])
t0, t1 = b['validation']['from_trick_7'], f1['validation']['from_trick_7']
print('from trick 7: in_best', t0['in_best'], t1['in_best'], '| regret', t0['regret'], t1['regret'], '| regret_gap_head', t0['regret_gap_head'], t1['regret_gap_head'], '| regret_random', t1['regret_random'], '| searched', t1['searched'], 'of', t1['n'])
PY

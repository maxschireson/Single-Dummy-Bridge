"""Run x8_match with counters on the scorer and the nets. Usage: instrument.py OUTJSON -- <x8_match args>"""
import os, sys
REPO = os.environ.get('REPO', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, os, json, time, runpy, atexit, collections
sys.path.insert(0, REPO)
out_path = sys.argv[1]; argv = sys.argv[sys.argv.index('--') + 1:]
from bridge_harness import gen6_nets, gen7_net
last = 0.
callers = collections.defaultdict(lambda: [0, 0.])
stats = collections.defaultdict(lambda: collections.Counter())
sizes = collections.defaultdict(collections.Counter)

def wrap(cls, name, tag, nfn):
    f = getattr(cls, name)
    def g(self, *a, **k):
        t = time.perf_counter(); r = f(self, *a, **k); dt = time.perf_counter() - t
        n = nfn(a, k)
        s = stats[tag]; s['calls'] += 1; s['rows'] += n; s['sec'] += dt
        sizes[tag][n] += 1
        if tag.startswith('net'):
            import inspect
            fr = inspect.stack(0)[2:6]
            who = '<'.join(f.function for f in fr)
            b = 'n<=2' if n <= 2 else ('n<=32' if n <= 32 else 'n>32')
            callers[f'{b} {who}'][0] += 1; callers[f'{b} {who}'][1] += dt
        global last
        if time.time() - last > 3:
            last = time.time(); dump()
        return r
    setattr(cls, name, g)

wrap(gen6_nets.FitScorer, 'log_score', 'scorer.log_score', lambda a, k: len(a[0]))
wrap(gen6_nets.FitScorer, 'type_log_score', 'scorer.type_log_score', lambda a, k: len(a[0]))
wrap(gen7_net.PolicyNet, 'log_policy_arrays', 'net.log_policy_arrays', lambda a, k: len(a[0]['state']))
wrap(gen7_net.PolicyNet, 'policy_and_gap_arrays', 'net.policy_and_gap', lambda a, k: len(a[0]['state']))

def dump():
    pid = os.getpid()
    d = {k: dict(v) for k, v in stats.items()}
    h = {k: sorted(((int(n), c) for n, c in v.items())) for k, v in sizes.items()}
    with open(f'{out_path}.{pid}.json', 'w') as fh:
        json.dump(dict(stats=d, sizes=h, callers=callers), fh)
import multiprocessing.util
multiprocessing.util.Finalize(None, dump, exitpriority=0)
atexit.register(dump)
sys.argv = ['x8_match.py'] + argv
runpy.run_path(os.path.join(REPO, 'scripts', 'x8_match.py'), run_name='__main__')

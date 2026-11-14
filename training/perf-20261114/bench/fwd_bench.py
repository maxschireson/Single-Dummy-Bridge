"""Rows/s of gen7_net.forward on a net, fp32 NumPy, synthetic inputs of the right shapes. One thread."""
import os, sys
REPO = os.environ.get('REPO', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
HERE = os.path.dirname(os.path.abspath(__file__))
import os, sys, time
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
sys.path.insert(0, REPO)
import numpy as np
from bridge_harness import gen7_net as g

def batch(n, rng):
    return dict(state=rng.integers(0, 11, (n, 52)).astype(np.uint8), order=rng.integers(0, 52, (n, 52)).astype(np.uint8),
                legal=rng.random((n, 52)) < .2, ctx=rng.random((n, g.N_CTX)).astype(np.float32),
                auction=(rng.random((n, g.N_AUCTION)) < .05).astype(np.uint8), shown=rng.random((n, g.N_SHOWN)).astype(np.float32),
                bot_own=np.zeros(n, np.int32), bot_other=np.zeros(n, np.int32))

def main(path, sizes=(64, 128, 256, 512, 1024)):
    with np.load(path) as z:
        p = {k: z[k] for k in z.files if k not in g.BANK_KEYS and k != 'bot_vocab'}
    rng = np.random.default_rng(0)
    macs = sum(np.prod(p[k].shape) * (4 if k in ('ws0', 'ws1', 'wd1') else 1) for k in ('ws0', 'ws1', 'wt0', 'wt1', 'wd1', 'wk'))
    macs += 4 * p['ws1'].shape[1] * p['wd0'].shape[1] + p['wt1'].shape[1] * p['wd0'].shape[1]
    print(f'MACs a row {macs/1e6:.2f} M')
    for n in sizes:
        b = batch(n, rng)
        g.forward(p, b)
        reps = max(3, int(20000 / n))
        t = time.perf_counter()
        for _ in range(reps):
            g.forward(p, b)
        dt = (time.perf_counter() - t) / reps
        print(f'n={n:5d}  {n/dt:9.0f} rows/s   {2*macs*n/dt/1e9:6.1f} GFLOP/s')
    # time split at 512
    import cProfile, pstats
    b = batch(512, rng)
    pr = cProfile.Profile(); pr.enable()
    for _ in range(40): g.forward(p, b)
    pr.disable(); pstats.Stats(pr).sort_stats('tottime').print_stats(8)

if __name__ == '__main__':
    main(sys.argv[1])

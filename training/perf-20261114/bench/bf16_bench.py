"""Bf16Forward rows/s by batch size, and RSS growth over many distinct batch sizes. One thread."""
import os, sys
REPO = os.environ.get('REPO', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
HERE = os.path.dirname(os.path.abspath(__file__))
import os, sys, time, resource
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
import numpy as np, torch
torch.set_num_threads(1)
from bridge_harness import gen7_net as g
from fwd_bench import batch
path = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else 'speed'
with np.load(path) as z:
    p = {k: z[k] for k in z.files if k not in g.BANK_KEYS and k != 'bot_vocab'}
f = g.Bf16Forward(p, torch)
rng = np.random.default_rng(0)
def rss(): return int(open('/proc/self/statm').read().split()[1]) * 4096 / 2**20
if mode == 'speed':
    for n in (1, 2, 8, 32, 64, 128, 256, 512, 1024):
        b = batch(n, rng); f(b); f(b)
        reps = max(5, int(20000 / n)); t = time.perf_counter()
        for _ in range(reps): f(b)
        dt = (time.perf_counter() - t) / reps
        print(f'n={n:5d} {n/dt:9.0f} rows/s  {dt*1e6:8.0f} us/call')
else:
    pad = mode == 'pad'
    print('start rss MB', round(rss()))
    t0 = time.perf_counter(); rows = 0
    for i in range(1, 3001):
        n = int(rng.integers(1, 700))
        m = n if not pad else (1 << (n - 1).bit_length())  # next power of two
        b = batch(m, rng); f(b); rows += m
        if i % 500 == 0:
            print(f'{i} calls  rss {rss():7.0f} MB  {time.perf_counter()-t0:6.1f} s')

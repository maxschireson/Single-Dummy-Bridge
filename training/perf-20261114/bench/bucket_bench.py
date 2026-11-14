import os, sys
REPO = os.environ.get('REPO', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
HERE = os.path.dirname(os.path.abspath(__file__))
import os, sys, time
sys.path.insert(0, REPO); sys.path.insert(0, HERE)
import numpy as np, torch
torch.set_num_threads(1)
from bridge_harness import gen7_net as g
from fwd_bench import batch
BUCKETS = [1, 2, 4, 8, 16, 24, 32, 48, 64, 80, 96, 128, 160, 192, 224, 256, 320, 384, 448, 512, 640, 768, 896, 1024]
def bucket(n):
    for b in BUCKETS:
        if n <= b: return b
    return -(-n // 256) * 256
with np.load(sys.argv[1]) as z:
    p = {k: z[k] for k in z.files if k not in g.BANK_KEYS and k != 'bot_vocab'}
f = g.Bf16Forward(p, torch); rng = np.random.default_rng(0)
def rss(): return int(open('/proc/self/statm').read().split()[1]) * 4096 / 2**20
t0 = time.perf_counter(); real = 0; done = 0
sizes = rng.integers(1, 700, 3000)
for i, n in enumerate(sizes, 1):
    m = bucket(int(n)); b = batch(m, rng); f(b); real += n; done += m
    if i % 1000 == 0: print(f'{i} calls rss {rss():6.0f} MB  {time.perf_counter()-t0:6.1f} s  real rows/s {real/(time.perf_counter()-t0):7.0f}  padding waste {done/real-1:.1%}')

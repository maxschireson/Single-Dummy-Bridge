"""Table values against pooled_ref.py (T4), independently of the C++ code: the file's header and entries are read
here, slots are unranked with endtable_ref.py, values computed with pooled_ref.py.
usage: check_values.py TABLE (all | SAMPLES) [SEED] [any | showout]
    all       every entry;  SAMPLES  random entries (seeded)
    showout   only entries whose exact lengths are all 0 or the suit's pool length (default: any knowledge)"""
import mmap, os, random, struct, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
from endtable_ref import Index
from pooled_ref import Pooled, SUIT

path, which = sys.argv[1], sys.argv[2]
seed = int(sys.argv[3]) if len(sys.argv) > 3 else 1
only = sys.argv[4] if len(sys.argv) > 4 else 'any'
f = open(path, 'rb')
mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
assert mm[:8] == b'SDBET001', 'not a table file'
version, k, kind, bits = struct.unpack_from('<4I', mm, 8)
entries, mN, mT, cN, cT = struct.unpack_from('<5Q', mm, 24)
assert (version, kind) == (1, 1)
t0 = time.time()
ix = Index(k)
assert (entries, mN, mT, cN, cT) == (ix.entries, ix.M['N'], ix.M['T'], len(ix.classes['N']), len(ix.classes['T'])), 'header counts differ from endtable_ref.py'


def entry(slot):
    bit = slot * bits
    w = mm[4096 + (bit >> 3)] | mm[4096 + (bit >> 3) + 1] << 8
    return (w >> (bit & 7)) & ((1 << bits) - 1)


rng = random.Random(seed)
n = bad = drawn = 0
hist = [0] * (k + 1)
it = range(entries) if which == 'all' else None
target = None if which == 'all' else int(which)
while True:
    if it is not None:
        if drawn >= entries:
            break
        slot = drawn
    else:
        if n >= target:
            break
        slot = rng.randrange(entries)
    drawn += 1
    hN, hS, pool, el, trump, leader = ix.unrank(slot)
    if only == 'showout':
        x = [bin(pool & SUIT[s]).count('1') for s in range(4)]
        if any(e is not None and x[s] and e not in (0, x[s]) for s, e in enumerate(el)):
            continue
    ref = Pooled(trump).value(hN, hS, pool, k, k, el, leader)
    got = entry(slot)
    n += 1
    hist[ref] += 1
    if got != ref:
        bad += 1
        if bad <= 5:
            print('MISMATCH slot', slot, 'table', got, 'pooled_ref', ref, (trump, leader, hex(hN), hex(hS), hex(pool), el))
print('%s: k=%d, %s entries (%s knowledge, seed %d): %d checked, %d mismatches; reference values by trick count %s (%.0f s)'
      % (os.path.basename(path), k, 'all' if which == 'all' else 'random', only, seed, n, bad, hist, time.time() - t0))
sys.exit(1 if bad else 0)

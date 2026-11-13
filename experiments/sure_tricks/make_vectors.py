"""Test vectors for the ending table: random slots with their canonical position and value.
Value from pooled_ref.py. Where the knowledge is show-outs only, the C++ search (sure_cpp --value) is run too
and must agree. Output: endtable_vectors.jsonl, one object per line: k, slot, line, value."""
import json, random, subprocess, sys, time
from endtable_ref import Index, line
from pooled_ref import Pooled, SUIT

COUNTS = {1: None, 2: 3000, 3: 2000, 4: 300}
rng = random.Random(21)
out = open('endtable_vectors.jsonl', 'w')
for k in (1, 2, 3, 4):
    t0 = time.time()
    ix = Index(k)
    slots = range(ix.entries) if COUNTS[k] is None else sorted(rng.sample(range(ix.entries), COUNTS[k]))
    rows, cpp_lines, cpp_rows = [], [], []
    for slot in slots:
        hN, hS, pool, el, trump, leader = ix.unrank(slot)
        v = Pooled(trump).value(hN, hS, pool, k, k, el, leader)
        rows.append(dict(k=k, slot=slot, line=line(hN, hS, pool, el, trump, leader), value=v))
        x = [bin(pool & SUIT[s]).count('1') for s in range(4)]
        if all(e is None or e in (0, x[s]) for s, e in enumerate(el)):
            vE = sum(1 << s for s in range(4) if x[s] and el[s] == 0)
            vW = sum(1 << s for s in range(4) if x[s] and el[s] == x[s])
            cpp_lines.append('%d %d %x %x %x %d %d %d %d' % (trump, leader, hN, hS, pool, k, k, vE, vW))
            cpp_rows.append(rows[-1])
    bad = 0
    if cpp_lines:
        res = subprocess.run(['./sure_cpp', '--value', '--keep'], input='\n'.join(cpp_lines) + '\n', capture_output=True, text=True, check=True).stdout.splitlines()
        for r, l in zip(cpp_rows, res):
            bad += json.loads(l)['value'] != r['value']
    for r in rows:
        out.write(json.dumps(r) + '\n')
    print('k=%d: %d vectors, %d of them show-out states checked against sure_cpp with %d mismatches (%.0f s)' % (k, len(rows), len(cpp_rows), bad, time.time() - t0), flush=True)

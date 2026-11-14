"""Summarize py-spy raw (collapsed) stacks: self and inclusive share by function, and by chosen buckets."""
import os, sys
REPO = os.environ.get('REPO', os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
HERE = os.path.dirname(os.path.abspath(__file__))
import sys, re, collections
path = sys.argv[1]
tot = 0
self_c = collections.Counter(); incl = collections.Counter()
stacks = []
for line in open(path):
    stack, _, n = line.rstrip().rpartition(' ')
    n = int(n); tot += n
    frames = stack.split(';')
    # frame like "forward (bridge_harness/gen7_net.py:213)"
    names = [re.sub(r':\d+\)$', ')', f) for f in frames]
    self_c[names[-1]] += n
    for f in set(names):
        incl[f] += n
    stacks.append((names, n))
print(f'samples {tot}')
print('\n-- inclusive top 45')
for f, n in incl.most_common(45):
    print(f'{100*n/tot:6.1f}%  {f}')
print('\n-- self top 30')
for f, n in self_c.most_common(30):
    print(f'{100*n/tot:6.1f}%  {f}')

"""Run the same sure_cpp input lines through several solver commands and compare per-card values.
usage: cmp_bins.py LINES NAME=CMD [NAME=CMD ...]     (the first is the reference)
Prints, for each other command: positions compared, positions with any card differing, card values higher / lower than
the reference, and up to five example lines."""
import json
import shlex
import subprocess
import sys


def run(cmd, path):
    with open(path) as f:
        r = subprocess.run(shlex.split(cmd), stdin=f, capture_output=True, text=True, check=True)
    return [json.loads(l) for l in r.stdout.splitlines()]


def main():
    path = sys.argv[1]
    specs = [a.split('=', 1) for a in sys.argv[2:]]
    lines = [l.strip() for l in open(path) if l.strip()]
    res = {name: run(cmd, path) for name, cmd in specs}
    ref_name = specs[0][0]
    ref = res[ref_name]
    secs = {name: sum(o.get('seconds', 0) for o in out) for name, out in res.items()}
    print('%s: %d positions, %.2f s' % (ref_name, len(ref), secs[ref_name]))
    for name, _ in specs[1:]:
        out = res[name]
        assert len(out) == len(ref)
        pos_diff = hi = lo = val_diff = 0
        ex = []
        for l, a, b in zip(lines, ref, out):
            ca, cb = a['cards'], b['cards']
            t = l.split()
            if t[0].startswith('N'):
                t = t[1:]
            decl = (int(t[1]) + len(t) - 9) % 2 == 0
            f = max if decl else min
            if ca and cb and f(ca.values()) != f(cb.values()):
                val_diff += 1
            d = False
            for c, v in cb.items():
                if c in ca and ca[c] != v:
                    d = True
                    hi += v > ca[c]
                    lo += v < ca[c]
            # value of the position for the side to move: max (declaring side) or min (defender) over cards
            if d:
                pos_diff += 1
                if len(ex) < 5:
                    ex.append((l, ca, cb))
        print('%s: %.2f s; %d of %d positions differ from %s in some card (higher %d, lower %d); position value differs in %d'
              % (name, secs[name], pos_diff, len(ref), ref_name, hi, lo, val_diff))
        for l, ca, cb in ex:
            print('   ', l, '|', ref_name, ca, '|', name, cb)


main()

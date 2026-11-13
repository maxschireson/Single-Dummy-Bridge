"""Two builds of the solver must give the same answers: position values on random 7- and 8-card positions and
per-card answers on the benchmark positions. For positions too large for the Python reference.
usage: check_cpp_builds.py OLD_BINARY NEW_BINARY"""
import json, random, subprocess, sys
from gen_table_positions import gen
D = json.load(open('bench_lines.json'))
rng = random.Random(123)
sets = [('benchmark positions, contract question', ''.join('N%d %s\n' % (D[k]['need'], D[k]['line']) for k in sorted(D)), []),
        ('benchmark positions, every card', ''.join(D[k]['line'] + '\n' for k in sorted(D) if int(k.split('_')[1]) <= 9), []),
        ('random 7-card positions', ''.join(gen(rng, 7) + '\n' for _ in range(600)), ['--value']),
        ('random 8-card positions', ''.join(gen(rng, 8) + '\n' for _ in range(250)), ['--value']),
        ('random 9-card positions', ''.join(gen(rng, 9) + '\n' for _ in range(60)), ['--value'])]
def run(binary, inp, flags):
    out = subprocess.run([binary, '--front', '4', *flags], input=inp, capture_output=True, text=True, check=True).stdout
    return [json.loads(l).get('value', json.loads(l).get('cards')) for l in out.splitlines()]
for name, inp, flags in sets:
    a, b = run(sys.argv[1], inp, flags), run(sys.argv[2], inp, flags)
    print('%s: %d positions, %d differ' % (name, len(a), sum(x != y for x, y in zip(a, b))), flush=True)

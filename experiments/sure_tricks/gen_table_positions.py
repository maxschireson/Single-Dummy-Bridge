"""Random k-card table entries, uniform over ordered positions (suit strings over N/S/unseen, relative ranks),
each with a random feasible show-out state. 80% trump, 20% notrump (the table's own mix). One sure_cpp input line each."""
import random, sys

def gen(rng, k):
    n = 4 * k
    while True:
        bars = sorted(rng.sample(range(n + 3), 3))
        parts = [bars[0], bars[1] - bars[0] - 1, bars[2] - bars[1] - 1, n + 2 - bars[2]]
        if max(parts) <= 13:
            break
    labels = ['N'] * k + ['S'] * k + ['X'] * (2 * k)
    rng.shuffle(labels)
    h = {'N': 0, 'S': 0, 'X': 0}
    xs, i = [], 0
    for s, L in enumerate(parts):
        seg = labels[i:i + L]; i += L
        for r, a in enumerate(seg):
            h[a] |= 1 << (13 * s + r)
        xs.append(seg.count('X'))
    while True:
        st = [rng.choice('FEW') if x else 'F' for x in xs]
        if sum(x for x, t in zip(xs, st) if t == 'E') <= k and sum(x for x, t in zip(xs, st) if t == 'W') <= k:
            break
    vE = sum(1 << s for s in range(4) if st[s] == 'E')
    vW = sum(1 << s for s in range(4) if st[s] == 'W')
    trump = rng.randrange(4) if rng.random() < 0.8 else 4
    return '%d %d %x %x %x %d %d %d %d' % (trump, rng.choice([0, 1]), h['N'], h['S'], h['X'], k, k, vE, vW)

if __name__ == '__main__':
    k, count = int(sys.argv[1]), int(sys.argv[2])
    rng = random.Random(11)
    for _ in range(count):
        print(gen(rng, k))

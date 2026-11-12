import numpy as np
rng = np.random.default_rng(7)

def boards(runs, n, lead, flat=0.75):
    """Heavy-tailed bounded board results: mostly flat, else a swing of 1..17 IMPs with a long tail; mean = lead."""
    sizes = np.arange(1, 18)
    p = 1 / sizes ** 1.3; p /= p.sum()
    mag = rng.choice(sizes, size=(runs, n), p=p)
    mean_mag = float(sizes @ p)
    up = 0.5 + lead / (2 * (1 - flat) * mean_mag)          # P(swing is in the candidate's favour)
    sign = np.where(rng.random((runs, n)) < up, 1, -1)
    x = np.where(rng.random((runs, n)) < flat, 0, sign * mag).astype(float)
    return x

def betting(x, alpha=0.05, cap=0.5, lead_null=0.0, sign=1):
    """First board at which the capital reaches 1/alpha (0 if never). sign=-1 with lead_null=d tests 'lead >= d'."""
    z = sign * (x - lead_null) / 24.0
    runs, n = z.shape
    s1 = np.zeros(runs); s2 = np.full(runs, (3 / 24) ** 2); cnt = np.ones(runs)      # one prior board at 0 with variance (3/24)^2
    logk = np.zeros(runs); hit = np.zeros(runs, int)
    for t in range(n):
        m = s1 / cnt; v = np.maximum(s2 / cnt - m * m, 1e-9)
        b = np.clip(m / (v + m * m), 0, cap)
        logk += np.log1p(b * z[:, t])
        s1 += z[:, t]; s2 += z[:, t] ** 2; cnt += 1
        new = (logk >= np.log(1 / alpha)) & (hit == 0)
        hit[new] = t + 1
    return hit

def hand_rule(x, first=1000, every=100):
    """Today's rule: from 1,000 boards, at every 100, promote if the 95% interval excludes zero on the high side."""
    runs, n = x.shape
    hit = np.zeros(runs, int)
    c1 = np.cumsum(x, axis=1); c2 = np.cumsum(x * x, axis=1)
    for t in range(first, n + 1, every):
        m = c1[:, t - 1] / t; sd = np.sqrt(np.maximum(c2[:, t - 1] / t - m * m, 1e-12))
        new = (m - 1.96 * sd / np.sqrt(t) > 0) & (hit == 0)
        hit[new] = t
    return hit

x0 = boards(4000, 6000, 0.0)
print('SD of a board: %.2f, flat share %.2f, kurtosis %.1f' % (x0.std(), (x0 == 0).mean(), ((x0 - x0.mean()) ** 4).mean() / x0.var() ** 2))
for lead in (0.0, 0.05, 0.1, 0.2, 0.4):
    x = x0 if lead == 0 else boards(2000, 6000, lead)
    h = betting(x); f = betting(x, alpha=0.10, lead_null=0.05, sign=-1); r = hand_rule(x)
    first = np.where((h > 0) & ((f == 0) | (h <= f)), 1, np.where(f > 0, -1, 0))        # which bound is reached first
    when = np.where(first == 1, h, np.where(first == -1, f, 6000))
    print('lead %.2f | betting: promoted %.3f, futility %.3f, undecided %.3f, median boards to a decision %d | hand rule: promoted %.3f, median boards %s'
          % (lead, (first == 1).mean(), (first == -1).mean(), (first == 0).mean(), np.median(when), (r > 0).mean(), int(np.median(r[r > 0])) if (r > 0).any() else '-'))
    print('          betting alone ever promotes: %.3f (median board %s)' % ((h > 0).mean(), int(np.median(h[h > 0])) if (h > 0).any() else '-'))

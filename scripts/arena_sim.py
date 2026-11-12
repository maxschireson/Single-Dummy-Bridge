#!/usr/bin/env python3
"""Arena simulator for Gen 9 (task G9-D2, experiment E9-5).

Gen 9 work in progress (dave). Not an arena tool: no board is played; per-board IMP results are
drawn from noise models fitted to the published feeds.

Two experiments:

  promotion  A candidate against the champion at a true gap (IMPs a board, candidate's side).
             Each run draws a stream of per-board results and applies three stopping rules:
               hand    the rule used by hand today: from 1,000 boards, every 100 to 5,000,
                       promote when a two-sided 95% t-interval's lower end is above zero
               mix     an always-valid interval: normal-mixture boundary with the running
                       variance plugged in (asymptotic), first look at 200 boards
               eb      an always-valid empirical-Bernstein interval for values in [-24, 24]
                       (predictable plug-in), exact for bounded data
             The always-valid rules promote when the lower end passes zero and stop for
             futility when the upper end falls below `futility` (default 0.05 IMPs).
             Output per (noise, gap, rule): promotion and futility rates, boards to a decision,
             and the fixed-sample size of equal power.

  schedule   Arenas of 8 to 20 players with true strengths spread like the published results,
             epochs of boards allocated by a schedule, ratings refitted after each epoch by
             weighted least squares, arrivals and departures. Output: root-mean-square rating
             error of active players against the truth, by boards played, per schedule.

Noise sources: Gaussian at a given SD, or a bootstrap of centred per-board values from a pool
(`pools` builds them from the rows of scripts/arena_feed_rows.py and optional fork-free match
rows such as g8's). A true gap is added to the centred values.

  python scripts/arena_sim.py pools --rows rows.jsonl.gz [--twin match/results.jsonl ...] --out pools.json.gz
  python scripts/arena_sim.py promotion --pools pools.json.gz --runs 2000 --out promotion.json
  python scripts/arena_sim.py schedule --pools pools.json.gz --runs 200 --out schedule.json

The always-valid forms here are dave's placeholders until G9-A4 specifies the arena's own; every
result names the form and parameters it used.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field, asdict
import gzip
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

BOUND = 24.0          # IMPs on one board are within 24 either way


# --------------------------------------------------------------------------- noise pools

POOL_PAIRS = {
    # centred per-board values of these pairs (common auction, dashboard counting rules) are pooled
    'twin': ('71s-32~7s-32',),
    'sibling': ('7s-32~6-32', '6-32~6-256'),
    'unrelated': ('6-32~ben', '7s-32~ben', '7s-32~ben64', '6-256~ben', '6-256~ben64', '6-32~5RZ32', '7s-32~5RZ32',
                  '6-32~3', '6-32~2', '6-32~1', '7s-32~1'),
}


def counted_rows(rows_path):
    """The dashboard's counting rules over arena_feed_rows output: snapshot cut-off, hidden and accidental
    cohorts out, allowed pairs, pairs in the dashboard's order, a deal family once per pair (earliest)."""
    import generation_results as gr
    kept = []
    with gzip.open(rows_path, 'rt') as f:
        for line in f:
            r = json.loads(line)
            if r['completed_epoch'] > r['snapshot_epoch']:
                continue
            try:
                p, flip = gr.normalize(r['pair'])
            except ValueError:
                p, flip = r['pair'], False
            m = gr.members(p)
            if any(x in gr.HIDDEN for x in m) or (p == '6-32~ben' and r['cohort'] in gr.ACCIDENTAL):
                continue
            if r['allowed_pairs'] and r['pair'] not in r['allowed_pairs']:
                continue
            s = -1 if flip else 1
            kept.append(dict(pair=p, family=r['family'], t=r['completed_epoch'], source=r['source'],
                             common=None if r['common'] is None else s * r['common'],
                             native=s * r['native'] if r['native_ok'] and r['native'] is not None else None))
    kept.sort(key=lambda r: r['t'])
    seen, out = set(), []
    for r in kept:
        key = (r['family'], r['pair'])
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def build_pools(rows_path, twin_files=(), regime='common'):
    rows = counted_rows(rows_path)
    by_pair = {}
    for r in rows:
        if r[regime] is not None:
            by_pair.setdefault(r['pair'], []).append(float(r[regime]))
    for path in twin_files:            # fork-free match rows: one JSON line a board with `common` from the first bot's side
        vals = [json.loads(line)[regime] for line in Path(path).read_text().splitlines() if line.strip()]
        by_pair.setdefault('twin-match:' + Path(path).name, []).extend(float(v) for v in vals if v is not None)
    pools = {}
    for name, pairs in POOL_PAIRS.items():
        members = [p for p in by_pair if p in pairs or (name == 'twin' and p.startswith('twin-match:'))]
        centred, flat = [], 0
        for p in members:
            x = np.array(by_pair[p])
            flat += int((x == 0).sum())
            centred.append(x - x.mean())       # each pair centred on its own mean: the pool is the noise shape only
        values = np.concatenate(centred) if centred else np.zeros(0)
        pools[name] = dict(pairs={p: len(by_pair[p]) for p in members}, n=int(values.size),
                           sd=float(values.std(ddof=1)) if values.size > 1 else None,
                           kurtosis=float(((values - values.mean()) ** 4).mean() / values.var() ** 2) if values.size > 1 else None,
                           flat=flat / values.size if values.size else None,
                           values=[round(float(v), 4) for v in values])
    pair_stats = {p: dict(n=len(v), mean=float(np.mean(v)), sd=float(np.std(v, ddof=1)) if len(v) > 1 else None)
                  for p, v in by_pair.items()}
    return dict(schema='arena-noise-pools-v1', regime=regime, pools=pools, pairs=pair_stats)


@dataclass
class Noise:
    """Per-board noise with mean zero: Gaussian at `sd`, or a bootstrap of a pool's centred values times `scale`."""
    name: str
    sd: float | None = None
    values: np.ndarray | None = None
    scale: float = 1.0

    def draw(self, rng, shape):
        if self.values is None:
            return rng.normal(0.0, self.sd * self.scale, size=shape).astype(np.float32)
        idx = rng.integers(0, self.values.size, size=shape)
        return (self.values[idx] * self.scale).astype(np.float32)

    @property
    def sigma(self):
        return self.sd * self.scale if self.values is None else float(self.values.std()) * self.scale


def load_pools(path):
    with gzip.open(path, 'rt') as f:
        doc = json.load(f)
    return {k: np.asarray(v['values'], dtype=np.float32) for k, v in doc['pools'].items()}


def noise_sources(pools):
    out = [Noise('gauss-2.6', sd=2.6), Noise('gauss-3.2', sd=3.2), Noise('gauss-4.2', sd=4.2)]
    for name in ('twin', 'sibling', 'unrelated'):
        if name in pools and pools[name].size:
            out.append(Noise('boot-' + name, values=pools[name]))
    if 'unrelated' in pools and pools['unrelated'].size:
        out.append(Noise('boot-unrelated-x2', values=pools['unrelated'], scale=2.0))
    return out


# --------------------------------------------------------------------------- stopping rules

@dataclass
class HandRule:
    first: int = 1000
    every: int = 100
    last: int = 5000
    z: float = 1.96              # replaced by the t quantile at each look
    name: str = 'hand'

    def run(self, X):
        """X: runs x boards. Returns decision (+1 promote, 0 none) and boards at decision (or at the last look)."""
        from scipy import stats
        runs, n = X.shape
        last = min(self.last, n)
        looks = np.arange(self.first, last + 1, self.every)
        c1 = np.cumsum(X, axis=1, dtype=np.float64)
        c2 = np.cumsum(X.astype(np.float64) ** 2, axis=1)
        decision = np.zeros(runs, np.int8)
        boards = np.full(runs, looks[-1], np.int64)
        open_ = np.ones(runs, bool)
        for t in looks:
            m = c1[:, t - 1] / t
            v = (c2[:, t - 1] - t * m * m) / (t - 1)
            lo = m - stats.t.ppf(0.975, t - 1) * np.sqrt(np.maximum(v, 0) / t)
            hit = open_ & (lo > 0)
            decision[hit], boards[hit] = 1, t
            open_ &= ~hit
        return decision, boards

    def params(self):
        return asdict(self)


def mixture_radius(t, var, alpha, rho2):
    """Two-sided normal-mixture boundary on the mean after t boards with variance var (Robbins; Howard et al. 2021)."""
    a = 1.0 + rho2 * var * t
    return np.sqrt(2.0 * a / rho2 * np.log(np.sqrt(a) / alpha)) / t


@dataclass
class MixtureCS:
    alpha: float = 0.05
    plan_sd: float = 3.5          # the mixture is tuned to be tightest near plan_boards at this SD
    plan_boards: int = 2000
    first: int = 200
    every: int = 50
    futility: float = 0.05
    name: str = 'mix'

    @property
    def rho2(self):
        c = -2 * math.log(self.alpha) + math.log(-2 * math.log(self.alpha) + 1)
        return c / (self.plan_sd ** 2 * self.plan_boards)

    def run(self, X):
        runs, n = X.shape
        looks = np.arange(self.first, n + 1, self.every)
        c1 = np.cumsum(X, axis=1, dtype=np.float64)
        c2 = np.cumsum(X.astype(np.float64) ** 2, axis=1)
        decision = np.zeros(runs, np.int8)
        boards = np.full(runs, n, np.int64)
        open_ = np.ones(runs, bool)
        for t in looks:
            m = c1[:, t - 1] / t
            v = np.maximum((c2[:, t - 1] - t * m * m) / (t - 1), 1e-6)
            r = mixture_radius(t, v, self.alpha, self.rho2)
            up = open_ & (m - r > 0)
            down = open_ & ~up & (m + r < self.futility)
            decision[up], boards[up] = 1, t
            decision[down], boards[down] = -1, t
            open_ &= ~(up | down)
            if not open_.any():
                break
        return decision, boards

    def params(self):
        return dict(asdict(self), rho2=self.rho2)


@dataclass
class EmpiricalBernsteinCS:
    """Predictable plug-in empirical-Bernstein confidence sequence (Waudby-Smith and Ramdas 2023, Thm 2) for
    values in [-BOUND, BOUND], mapped to [0, 1]."""
    alpha: float = 0.05
    cap: float = 0.5
    every: int = 50
    first: int = 50
    futility: float = 0.05
    name: str = 'eb'

    def run(self, X):
        runs, n = X.shape
        Y = (X.astype(np.float64) + BOUND) / (2 * BOUND)
        la = math.log(2 / self.alpha)
        s_y = np.zeros(runs)            # running sums for the plug-in mean and variance
        s_dev = np.zeros(runs)
        mu_prev = np.full(runs, 0.5)    # mean estimate before board t, with the 1/2 prior
        var_prev = np.full(runs, 0.25)
        S_l = np.zeros(runs); S_ly = np.zeros(runs); S_vpsi = np.zeros(runs)
        decision = np.zeros(runs, np.int8)
        boards = np.full(runs, n, np.int64)
        open_ = np.ones(runs, bool)
        for t in range(1, n + 1):
            y = Y[:, t - 1]
            lam = np.minimum(np.sqrt(2 * la / (var_prev * t * math.log(1 + t))), self.cap)
            v = 4 * (y - mu_prev) ** 2
            psi = (-np.log1p(-lam) - lam) / 4
            S_l += lam; S_ly += lam * y; S_vpsi += v * psi
            s_y += y
            mu = (0.5 + s_y) / (t + 1)
            s_dev += (y - mu) ** 2
            var_prev = (0.25 + s_dev) / (t + 1)
            mu_prev = mu
            if t >= self.first and t % self.every == 0:
                centre = S_ly / S_l
                radius = (la + S_vpsi) / S_l
                lo = (centre - radius) * 2 * BOUND - BOUND
                hi = (centre + radius) * 2 * BOUND - BOUND
                up = open_ & (lo > 0)
                down = open_ & ~up & (hi < self.futility)
                decision[up], boards[up] = 1, t
                decision[down], boards[down] = -1, t
                open_ &= ~(up | down)
                if not open_.any():
                    break
        return decision, boards

    def params(self):
        return asdict(self)


def fixed_sample_size(power, gap, sigma, alpha_one_sided=0.025):
    """Boards a single fixed-sample one-sided z test needs for this power at this gap."""
    from scipy import stats
    if gap <= 0 or not 0 < power < 1:
        return None
    p = min(max(power, 1e-3), 0.999)
    return ((stats.norm.ppf(1 - alpha_one_sided) + stats.norm.ppf(p)) * sigma / gap) ** 2


def promotion(noises, gaps, rules, runs=2000, cap=40000, chunk=250, seed=9):
    out = []
    for ni, noise in enumerate(noises):
        for gi, gap in enumerate(gaps):
            rng = np.random.default_rng([seed, ni, gi])
            res = {r.name: dict(decision=[], boards=[]) for r in rules}
            started = time.time()
            for c0 in range(0, runs, chunk):
                k = min(chunk, runs - c0)
                X = noise.draw(rng, (k, cap)) + np.float32(gap)
                for rule in rules:
                    d, b = rule.run(X)
                    res[rule.name]['decision'].append(d)
                    res[rule.name]['boards'].append(b)
                del X
            for rule in rules:
                d = np.concatenate(res[rule.name]['decision'])
                b = np.concatenate(res[rule.name]['boards'])
                promoted = d == 1
                decided = d != 0
                row = dict(noise=noise.name, sigma=round(noise.sigma, 3), gap=gap, rule=rule.name, runs=runs, cap=cap,
                           promote=float(promoted.mean()), promote_se=float(math.sqrt(max(promoted.mean() * (1 - promoted.mean()), 1e-12) / runs)),
                           futility=float((d == -1).mean()), undecided=float((~decided).mean()),
                           median_boards_decided=float(np.median(b[decided])) if decided.any() else None,
                           median_boards_promoted=float(np.median(b[promoted])) if promoted.any() else None,
                           mean_boards=float(b.mean()))
                # Boards by which a share q of all runs had promoted, against the boards one fixed-sample test
                # needs for power q at this gap: the price of being allowed to look at every board.
                t_promote = np.where(promoted, b, np.inf)
                for q in (0.8, 0.9):
                    tag = int(q * 100)
                    n_seq = float(np.quantile(t_promote, q)) if promoted.mean() >= q else None
                    n_fix = fixed_sample_size(q, gap, noise.sigma)
                    row[f'boards_to_power{tag}'] = n_seq
                    row[f'fixed_boards_power{tag}'] = None if n_fix is None else round(n_fix)
                    row[f'ratio_power{tag}'] = round(n_seq / n_fix, 3) if n_seq and n_fix else None
                out.append(row)
            print(f'{noise.name:20s} gap {gap:+.2f}: ' + '  '.join(
                f"{r['rule']} P={r['promote']:.3f} F={r['futility']:.3f} med={r['median_boards_decided']}"
                for r in out[-len(rules):]) + f'  ({time.time() - started:.0f}s)', flush=True)
    return out


# --------------------------------------------------------------------------- ratings and schedules

PUBLISHED = {   # strengths relative to Gen 6 fast, common auction, from the published pair means (12 Nov)
    '71s-32': 0.26, '7s-32': 0.26, '6-256': 0.13, 'ben64': 0.19, 'ben': 0.11, '6-32': 0.0,
    '5RZ32': -0.73, '3': -0.70, '2': -0.71, '1': -1.67}


def fit_ratings(n, sums, sq, players, prior_var=16.0, k=50.0, ridge=1e-6):
    """Weighted least squares on pair means. n, sums, sq: (P, P) upper-triangular board counts, sums and sums of
    squares of results from the row player's side. Per-pair variance is the pair's sample variance shrunk toward
    prior_var with weight k boards. Returns ratings centred on `players` and the information matrix."""
    P = n.shape[0]
    I = np.zeros((P, P)); b = np.zeros(P)
    iu, ju = np.nonzero(np.triu(n, 1))
    for i, j in zip(iu, ju):
        cnt = n[i, j]
        m = sums[i, j] / cnt
        sv = (sq[i, j] - cnt * m * m) / (cnt - 1) if cnt > 1 else prior_var
        v = (max(cnt - 1, 0) * sv + k * prior_var) / (max(cnt - 1, 0) + k)
        w = cnt / v
        I[i, i] += w; I[j, j] += w; I[i, j] -= w; I[j, i] -= w
        b[i] += w * m; b[j] -= w * m
    A = np.zeros(P); A[players] = 1.0
    M = I + np.outer(A, A) + ridge * np.eye(P)      # sum over active players fixed at zero
    s = np.linalg.solve(M, b)
    s = s - s[players].mean()
    return s, I


@dataclass
class ArenaSpec:
    players: int = 12
    lineages: int = 4
    epochs: int = 15
    boards_per_epoch: int = 2000
    turnover_every: int = 2           # one arrival and one departure every this many epochs
    chunk: int = 50                   # boards per allocation step
    pair_effect: float = 0.0          # one pair beats the model by this much
    noisy_player: bool = False        # one player's boards have twice the noise
    anchors: int = 2


def simulate_arena(spec, schedule, pools, rng):
    """One arena. Returns RMSE of active players' fitted ratings (centred) against truth after each epoch."""
    base = np.array(list(PUBLISHED.values()))
    cap = spec.players + spec.epochs // max(spec.turnover_every, 1) + 2
    truth = np.zeros(cap); lineage = np.zeros(cap, int); scale = np.ones(cap)
    def new_player(i):
        truth[i] = rng.choice(base) + rng.normal(0, 0.15)
        lineage[i] = rng.integers(spec.lineages)
    for i in range(spec.players):
        new_player(i)
    if spec.noisy_player:
        scale[spec.players - 1] = 2.0
    active = list(range(spec.players)); nxt = spec.players
    anchors = active[:spec.anchors]
    effect = np.zeros((cap, cap))
    if spec.pair_effect:
        i, j = active[-2], active[-3]
        effect[i, j], effect[j, i] = spec.pair_effect, -spec.pair_effect
    n = np.zeros((cap, cap)); sums = np.zeros((cap, cap)); sq = np.zeros((cap, cap))
    sib, unr = pools['sibling'], pools['unrelated']
    rmse, boards_total = [], 0
    for e in range(spec.epochs):
        if e and spec.turnover_every and e % spec.turnover_every == 0:
            leave = [p for p in active if p not in anchors]
            active.remove(leave[rng.integers(len(leave))])
            new_player(nxt); active.append(nxt); nxt += 1
        s_hat, I = fit_ratings(n, sums, sq, active)
        champion = max(active, key=lambda p: s_hat[p]) if boards_total else active[0]
        alloc = allocate(schedule, spec, active, anchors, champion, n, sums, sq, I, rng)
        for (i, j), cnt in alloc.items():
            if cnt <= 0:
                continue
            a, b_ = (i, j) if i < j else (j, i)
            pool = sib if lineage[a] == lineage[b_] else unr
            x = pool[rng.integers(0, pool.size, cnt)] * max(scale[a], scale[b_]) + (truth[a] - truth[b_] + effect[a, b_])
            n[a, b_] += cnt; sums[a, b_] += x.sum(); sq[a, b_] += (x * x).sum()
        boards_total += spec.boards_per_epoch
        s_hat, _ = fit_ratings(n, sums, sq, active)
        t = truth[active] - truth[active].mean()
        rmse.append(float(np.sqrt(np.mean((s_hat[active] - t) ** 2))))
    return rmse


def allocate(schedule, spec, active, anchors, champion, n, sums, sq, I, rng):
    pairs_all = [(a, b) for k, a in enumerate(active) for b in active[k + 1:]]
    B = spec.boards_per_epoch
    if schedule == 'equal':
        pairs = pairs_all
    elif schedule == 'star':
        hubs = [champion] + [a for a in anchors if a != champion]
        pairs = sorted({tuple(sorted((h, x))) for h in hubs for x in active if x != h})
    elif schedule == 'variance':
        return allocate_variance(spec, active, n, sums, sq, pairs_all)
    else:
        raise ValueError(schedule)
    per = np.full(len(pairs), B // len(pairs))
    per[rng.permutation(len(pairs))[:B - per.sum()]] += 1
    return dict(zip(pairs, per))


def allocate_variance(spec, active, n, sums, sq, pairs, prior_var=16.0, k=50.0):
    """Greedy: each chunk of boards goes to the pair that most reduces the summed variance of the centred ratings
    of active players, given the information already gathered (Sherman-Morrison on the pseudo-inverse)."""
    idx = {p: i for i, p in enumerate(active)}
    A = len(active)
    I = np.zeros((A, A))
    var = {}
    for a, b in pairs:
        i, j = (a, b) if a < b else (b, a)
        cnt = n[i, j]
        if cnt > 1:
            m = sums[i, j] / cnt
            sv = (sq[i, j] - cnt * m * m) / (cnt - 1)
            v = ((cnt - 1) * sv + k * prior_var) / (cnt - 1 + k)
        else:
            v = prior_var
        var[(a, b)] = v
        if cnt:
            w = cnt / v; x, y = idx[a], idx[b]
            I[x, x] += w; I[y, y] += w; I[x, y] -= w; I[y, x] -= w
    J = np.ones((A, A)) / A
    alloc = {p: 0 for p in pairs}
    steps = spec.boards_per_epoch // spec.chunk
    for _ in range(steps):
        S = np.linalg.inv(I + J + 1e-6 * np.eye(A)) - J      # covariance of centred ratings (I + J is invertible once connected)
        S2 = S @ S
        best, gain = None, -1.0
        for (a, b) in pairs:
            x, y = idx[a], idx[b]
            w = spec.chunk / var[(a, b)]
            aSa = S[x, x] + S[y, y] - 2 * S[x, y]
            aS2a = S2[x, x] + S2[y, y] - 2 * S2[x, y]
            g = w * aS2a / (1 + w * aSa)
            if g > gain:
                best, gain = (a, b), g
        a, b = best
        alloc[best] += spec.chunk
        w = spec.chunk / var[best]; x, y = idx[a], idx[b]
        I[x, x] += w; I[y, y] += w; I[x, y] -= w; I[y, x] -= w
    return alloc


def schedule_experiment(pools, runs=200, sizes=(8, 12, 20), schedules=('equal', 'star', 'variance'), slices=None, seed=9):
    slices = slices or {'base': {}, 'pair-effect-0.3': dict(pair_effect=0.3), 'noisy-player-x2': dict(noisy_player=True)}
    out = []
    for size in sizes:
        for sname, extra in slices.items():
            spec = ArenaSpec(players=size, **extra)
            for sched in schedules:
                started = time.time()
                curves = np.array([simulate_arena(spec, sched, pools, np.random.default_rng([seed, size, r]))
                                   for r in range(runs)])
                mean = curves.mean(axis=0)
                out.append(dict(players=size, slice=sname, schedule=sched, runs=runs, spec=asdict(spec),
                                boards=[spec.boards_per_epoch * (e + 1) for e in range(spec.epochs)],
                                rmse=[round(float(v), 4) for v in mean],
                                rmse_se=[round(float(v), 4) for v in curves.std(axis=0, ddof=1) / math.sqrt(runs)]))
                print(f'{size:2d} players {sname:16s} {sched:9s} RMSE after epochs 1, 5, 15: '
                      f'{mean[0]:.3f} {mean[min(4, len(mean) - 1)]:.3f} {mean[-1]:.3f} ({time.time() - started:.0f}s)', flush=True)
    return out


# --------------------------------------------------------------------------- command line

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('pools'); p.add_argument('--rows', type=Path, required=True); p.add_argument('--twin', type=Path, nargs='*', default=[])
    p.add_argument('--regime', default='common'); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('promotion'); p.add_argument('--pools', type=Path, required=True); p.add_argument('--runs', type=int, default=2000)
    p.add_argument('--cap', type=int, default=40000); p.add_argument('--gaps', type=float, nargs='*', default=[0, 0.05, 0.1, 0.2, 0.4])
    p.add_argument('--noise', nargs='*'); p.add_argument('--rules', nargs='*', default=['hand', 'mix', 'eb'])
    p.add_argument('--futility', type=float, default=0.05); p.add_argument('--out', type=Path, required=True); p.add_argument('--seed', type=int, default=9)
    p.add_argument('--plan-boards', type=int, default=2000); p.add_argument('--plan-sd', type=float, default=3.5); p.add_argument('--alpha', type=float, default=0.05)
    p = sub.add_parser('schedule'); p.add_argument('--pools', type=Path, required=True); p.add_argument('--runs', type=int, default=200)
    p.add_argument('--sizes', type=int, nargs='*', default=[8, 12, 20]); p.add_argument('--out', type=Path, required=True); p.add_argument('--seed', type=int, default=9)
    a = ap.parse_args()
    if a.cmd == 'pools':
        doc = build_pools(a.rows, a.twin, a.regime)
        with gzip.open(a.out, 'wt') as f:
            json.dump(doc, f, separators=(',', ':'))
        for k, v in doc['pools'].items():
            print(k, v['n'], 'boards, sd', round(v['sd'], 3), 'kurtosis', round(v['kurtosis'], 1), 'pairs', v['pairs'])
        return
    pools = load_pools(a.pools)
    started = time.time()
    if a.cmd == 'promotion':
        noises = [n for n in noise_sources(pools) if not a.noise or n.name in a.noise]
        makers = dict(hand=lambda: HandRule(), mix=lambda: MixtureCS(alpha=a.alpha, futility=a.futility, plan_boards=a.plan_boards, plan_sd=a.plan_sd),
                      eb=lambda: EmpiricalBernsteinCS(alpha=a.alpha, futility=a.futility))
        rules = [makers[r]() for r in a.rules]
        rows = promotion(noises, a.gaps, rules, runs=a.runs, cap=a.cap, seed=a.seed)
        doc = dict(experiment='E9-5 promotion', rules={r.name: r.params() for r in rules}, pools=str(a.pools), results=rows)
    else:
        rows = schedule_experiment(pools, runs=a.runs, sizes=a.sizes, seed=a.seed)
        doc = dict(experiment='E9-5 schedule', pools=str(a.pools), results=rows)
    doc.update(computed_utc=time.strftime('%Y-%m-%d %H:%M', time.gmtime()), cpu_seconds=round(time.process_time(), 1),
               wall_seconds=round(time.time() - started, 1), seed=a.seed)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(doc, indent=1))


if __name__ == '__main__':
    main()

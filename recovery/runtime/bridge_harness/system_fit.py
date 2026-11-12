"""Training a system-aware hand-fit scorer: data from mixed tables, model, trainer.

Work in progress (Gen 8 system layer, not the final form, used by no arena bot): docs/gen8_systems.md.

Data. Random deals are bid at a table where each side has its own bidder (and so its own
system). For every seat the true hand is a positive example; alternative hands (some random,
some the true hand with a few cards swapped) are labelled by replaying that seat's calls with
the alternative hand through the seat's own bidder. This is the Gen 6 scorer's recipe
(research/joint-auction-belief-20261110, analysis/auction_belief/gen_fit.py) with the bidder
behind an interface (system_bidders.py) and one bidder per side.

Model. system_nets.SystemFitScorer: a shared call table plus one correction table per system,
and FitScorer's layers after that. Trained on three views of each example: both systems
declared, both hidden, and each side hidden with probability 1/2. Hidden rows teach the
shared table to stand alone, which is the reading used for 'unknown'.

Nothing here fixes the systems or their number. `add_system` appends a zero correction, which
reads as 'unknown' until trained, and `train(only=...)` trains that correction with every
other array frozen, so the systems already in a file are untouched.
"""
import json
import time

import numpy as np

from .gen6_nets import BITS5, EYE14, EYE38, HON_HCP, MAX_SLOTS, N_CALLS, POP, hand_types
from .system_bidders import VUL_EW, VUL_NS
from .system_nets import D_AUC, OWN_ROWS
from .systems import UNKNOWN

DATA_SCHEMA = 'system-fit-data-v1'
MODEL_SCHEMA = 'system-fit-scorer-v1'
D_HAND = 56 + 20 + 4 + 38 + 2
K_RAND, K_NEAR = 3, 5
OWN_COLS = OWN_ROWS.astype(np.float32)
STATS = dict(unrepeated=[0., 0.], deals=[0, 0])      # per side of the last generate() calls: true hands whose replay differed
LAYERS = ('Wh', 'b0', 'W1', 'b1', 'W2', 'b2', 'Wo', 'bo')


# ---- data -------------------------------------------------------------------------------

def deal(rng, n):
    """n random deals: hands (n,4,13) card ids, dealer (n,), vulnerability index (n,)."""
    deck = rng.permuted(np.broadcast_to(np.arange(52), (n, 52)), axis=1)
    return deck.reshape(n, 4, 13), rng.integers(0, 4, n), rng.integers(0, 4, n)


def simulate(bidders, hands, dealer, vul, max_calls=44):
    """Greedy auctions in lockstep; North and South bid with bidders[0], East and West with
    bidders[1]. Returns calls (-1 padded), length, contract (ended with a bid made), legal."""
    B = len(hands)
    sessions = [bidders[s % 2].session(hands[:, s], np.full(B, s), dealer, vul) for s in range(4)]
    calls = np.full((B, max_calls), -1, np.int8)
    legal_log = np.zeros((B, max_calls, 40), bool)
    last_order, last_seat = np.full(B, -1), np.full(B, -1)
    doubled, passes, active = np.zeros(B, np.int64), np.zeros(B, np.int64), np.ones(B, bool)
    orders = np.arange(35)
    for t in range(max_calls):
        idx = np.flatnonzero(active)
        if not len(idx):
            break
        seat = (dealer[idx] + t) % 4
        lo, ls, db = last_order[idx], last_seat[idx], doubled[idx]
        legal = np.zeros((len(idx), 40), bool)
        legal[:, 2] = True
        legal[:, 5:] = orders[None, :] > lo[:, None]
        legal[:, 3] = (lo >= 0) & (db == 0) & (seat % 2 != ls % 2)
        legal[:, 4] = (db == 1) & (seat % 2 == ls % 2)
        call = np.empty(len(idx), np.int64)
        for s in range(4):
            sel = seat == s
            if sel.any():
                call[sel] = sessions[s].act(idx[sel], calls[idx[sel]].astype(np.int64), np.full(int(sel.sum()), t), legal[sel])
        calls[idx, t] = call
        legal_log[idx, t] = legal
        made = call >= 5
        last_order[idx[made]] = call[made] - 5
        last_seat[idx[made]] = seat[made]
        doubled[idx[made]] = 0
        passes[idx] = np.where(call == 2, passes[idx] + 1, 0)
        doubled[idx[call == 3]] = 1
        doubled[idx[call == 4]] = 2
        ended = ((passes[idx] >= 3) & (last_order[idx] >= 0)) | ((passes[idx] >= 4) & (last_order[idx] < 0))
        active[idx[ended]] = False
    return dict(calls=calls, length=(calls >= 0).sum(1), contract=~active & (last_order >= 0), legal=legal_log)


def alternatives(rng, hands):
    """(B,4,13) true hands -> (B,4,K,13): K_RAND random hands, then K_NEAR hands with 1-8 cards swapped."""
    B = len(hands)
    out = np.empty((B, 4, K_RAND + K_NEAR, 13), np.int64)
    out[:, :, :K_RAND] = np.argsort(rng.random((B, 4, K_RAND, 52)), axis=-1)[..., :13]
    member = np.zeros((B, 4, 52), bool)
    np.put_along_axis(member, hands, True, axis=2)
    for k in range(K_NEAR):
        swaps = rng.integers(1, 9, (B, 4))
        held = np.argsort(rng.random((B, 4, 52)) + ~member * 10, axis=-1)[..., :13]       # the hand, shuffled
        other = np.argsort(rng.random((B, 4, 52)) + member * 10, axis=-1)[..., :13]       # 13 cards outside it
        out[:, :, K_RAND + k] = np.where(np.arange(13)[None, None, :] < swaps[..., None], other, held)
    return out


def label(bidders, alt, sim, dealer, vul):
    """Would each alternative hand (B,4,K,13) have made every call its seat made? Each seat
    is replayed by its own side's bidder."""
    B, _, K, _ = alt.shape
    calls, length, legal = sim['calls'].astype(np.int64), sim['length'], sim['legal']
    d = np.repeat(np.arange(B), K)
    out = np.zeros((B, 4, K), bool)
    for s in range(4):
        session = bidders[s % 2].session(alt[:, s].reshape(B * K, 13), np.full(B * K, s), dealer[d], vul[d])
        first = (s - dealer[d]) % 4
        alive = np.ones(B * K, bool)
        for j in range(calls.shape[1] // 4 + 1):
            turn = first + 4 * j
            rows = np.flatnonzero(alive & (turn < length[d]))
            if not len(rows):
                break
            dd, tt = d[rows], turn[rows]
            alive[rows[session.act(rows, calls[dd], tt, legal[dd, tt]) != calls[dd, tt]]] = False
        out[:, s] = alive.reshape(B, K)
    return out


def generate(rng, bidders, n_deals, chunk=768):
    """Examples from n_deals deals bid at one table, bidders = (North-South, East-West)."""
    K = K_RAND + K_NEAR
    D, E, n = dict(calls=[], dealer=[], vul=[]), dict(deal=[], seat=[], length=[], hon=[], label=[], kind=[]), 0
    while n < n_deals:
        hands, dealer, vul = deal(rng, chunk)
        sim = simulate(bidders, hands, dealer, vul)
        keep = np.flatnonzero(sim['contract'] & (sim['length'] + 3 <= MAX_SLOTS))[:n_deals - n]
        alt = alternatives(rng, hands)
        again = label(bidders, hands[:, :, None, :], sim, dealer, vul)[keep][:, :, 0]
        for side in (0, 1):                     # a bidder must repeat itself, unless it says it may not (then the rate is recorded)
            missed = float(1 - again[:, side::2].mean())
            if missed and getattr(bidders[side], 'repeatable', True):
                raise RuntimeError('a true hand did not reproduce its own calls: the bidder is not a function of hand and auction')
            STATS['unrepeated'][side] += missed * len(keep)
            STATS['deals'][side] += len(keep)
        labels = np.concatenate([np.ones((len(keep), 4, 1), bool), label(bidders, alt, sim, dealer, vul)[keep]], axis=2)
        member = np.zeros((len(keep), 4, 1 + K, 52), np.int8)
        np.put_along_axis(member, np.concatenate([hands[:, :, None, :], alt], axis=2)[keep], 1, axis=3)
        ln, hon = hand_types(member)
        D['calls'].append(sim['calls'][keep][:, :MAX_SLOTS]); D['dealer'].append(dealer[keep].astype(np.int8)); D['vul'].append(vul[keep].astype(np.int8))
        E['deal'].append(np.repeat(n + np.arange(len(keep)), 4 * (1 + K)).astype(np.int32))
        E['seat'].append(np.tile(np.repeat(np.arange(4), 1 + K), len(keep)).astype(np.int8))
        E['length'].append(ln.reshape(-1, 4).astype(np.int8)); E['hon'].append(hon.reshape(-1, 4).astype(np.int8))
        E['label'].append(labels.reshape(-1))
        E['kind'].append(np.tile(np.array([0] + [1] * K_RAND + [2] * K_NEAR, np.int8), len(keep) * 4))
        n += len(keep)
    out = {'d_' + k: np.concatenate(v) for k, v in D.items()}
    out.update({k: np.concatenate(v) for k, v in E.items()})
    return out


def merge(parts):
    """Join data sets (each with its own `systems` list) into one with a common list.

    A part is a dict with the arrays of generate() plus systems (ids), generators (their
    sha256) and d_sys (deals, 2): the index of the North-South and East-West system."""
    systems, generators, out, offset = [], {}, {}, 0
    for q in parts:
        ids = [str(s) for s in q['systems']]
        for s, g in zip(ids, q['generators']):
            if generators.setdefault(s, str(g)) != str(g):
                raise ValueError(f'system {s} was generated by two different bidders')
            if s not in systems:
                systems.append(s)
        remap = np.array([systems.index(s) for s in ids])
        for k, v in q.items():
            if k in ('systems', 'generators', 'schema'):
                continue
            v = remap[v] if k == 'd_sys' else v + offset if k == 'deal' else v
            out.setdefault(k, []).append(v)
        offset += len(q['d_dealer'])
    out = {k: np.concatenate(v) for k, v in out.items()}
    out.update(systems=np.array(systems), generators=np.array([generators[s] for s in systems]), schema=np.array(DATA_SCHEMA))
    return out


def load_data(paths):
    parts = []
    for path in paths:
        with np.load(path, allow_pickle=False) as z:
            if str(z['schema']) != DATA_SCHEMA:
                raise ValueError(f'{path}: not {DATA_SCHEMA}')
            parts.append({k: z[k] for k in z.files})
    return merge(parts)


# ---- model ------------------------------------------------------------------------------

class Model:
    """Weights of a SystemFitScorer with its systems. Wa is (K, 28*38, H); table k = 0 is
    shared and table i belongs to sys_ids[i]."""

    def __init__(self, p, sys_ids):
        self.p, self.sys_ids = p, list(sys_ids)
        if self.sys_ids[0] != UNKNOWN or len(p['Wa']) != len(self.sys_ids):
            raise ValueError('one table per system, the first of them shared and named unknown')

    @classmethod
    def new(cls, systems=(), seed=0, widths=(768, 512, 256)):
        rng = np.random.default_rng(seed)
        w = lambda i, o: (rng.standard_normal((i, o)) * np.sqrt(2.0 / i)).astype(np.float32)
        p = dict(Wh=w(D_HAND, widths[0]), Wa=(rng.standard_normal((1, D_AUC, widths[0])) * 0.05).astype(np.float32), b0=np.zeros(widths[0], np.float32),
                 W1=w(widths[0], widths[1]), b1=np.zeros(widths[1], np.float32), W2=w(widths[1], widths[2]), b2=np.zeros(widths[2], np.float32),
                 Wo=w(widths[2], 1) * np.float32(0.1), bo=np.zeros(1, np.float32))
        model = cls(p, [UNKNOWN])
        for s in systems:
            model.add_system(s)
        return model

    @classmethod
    def load(cls, path):
        """A system-aware file, or a pre-system FitScorer file (its table becomes the shared one)."""
        with np.load(path, allow_pickle=False) as z:
            p = {k: z[k] for k in LAYERS + ('Wa',)}
            ids = [str(s) for s in z['sys_ids']] if 'sys_ids' in z.files else [UNKNOWN]
            gate = z['sys_gate'] if 'sys_gate' in z.files else np.ones((1, 1))
        if p['Wa'].ndim == 2:
            p['Wa'] = p['Wa'][None]
        if not np.array_equal(gate, cls.gate_for(len(ids))):
            raise ValueError(f'{path}: not a shared-plus-correction file; this trainer cannot continue it')
        return cls(p, ids)

    @staticmethod
    def gate_for(n):
        gate = np.eye(n, dtype=np.float32)
        gate[:, 0] = 1
        return gate

    @property
    def gate(self):
        return self.gate_for(len(self.sys_ids))

    def add_system(self, system):
        """Append a system with a zero correction: it reads as 'unknown' until trained."""
        if system in self.sys_ids:
            raise ValueError(f'{system} is already in this model')
        self.sys_ids.append(str(system))
        self.p['Wa'] = np.concatenate([self.p['Wa'], np.zeros((1,) + self.p['Wa'].shape[1:], np.float32)])

    def index(self, systems):
        """Model rows of a list of system ids; 0 for ids this model does not have."""
        return np.array([self.sys_ids.index(s) if s in self.sys_ids else 0 for s in systems])

    def save(self, path, meta=None):
        np.savez(path, **self.p, sys_ids=np.array(self.sys_ids), sys_gate=self.gate,
                 meta=np.array(json.dumps(dict(meta or {}, schema=MODEL_SCHEMA), sort_keys=True)))


def hand_features(length, hon, own_vul, opp_vul):
    length, hon = np.asarray(length).astype(np.int64), np.asarray(hon).astype(np.int64)
    n = len(length)
    v = np.empty((n, 2), np.float32)
    v[:, 0], v[:, 1] = own_vul, opp_vul
    return np.concatenate([EYE14[length].reshape(n, 56), BITS5[hon].reshape(n, 20), ((length - POP[hon]) / 8.0).astype(np.float32),
                           EYE38[HON_HCP[hon].sum(axis=1)], v], axis=1)


def auction_onehot(calls, dealer, seat):
    """calls (n,T) tokens with -1 padding -> seat-aligned (n, 28*38) one-hot."""
    calls = np.asarray(calls).astype(np.int64)
    pos = ((np.asarray(dealer) - np.asarray(seat)) % 4)[:, None] + np.arange(calls.shape[1])[None, :]
    oh = np.zeros((len(calls), D_AUC + 1), np.float32)
    np.put_along_axis(oh, np.where((calls >= 0) & (pos < MAX_SLOTS), pos * N_CALLS + calls - 2, D_AUC), 1.0, axis=1)
    return oh[:, :-1]


def batch(model, d, ix, table=None):
    """Inputs for examples ix: hand features, auction one-hot, labels, and the model rows of
    the own and opposing systems (before any view is applied)."""
    dl, seat = d['deal'][ix], d['seat'][ix].astype(np.int64)
    vul = d['d_vul'][dl].astype(np.int64)
    ns = seat % 2 == 0
    xh = hand_features(d['length'][ix], d['hon'][ix], np.where(ns, VUL_NS[vul], VUL_EW[vul]), np.where(ns, VUL_EW[vul], VUL_NS[vul]))
    xa = auction_onehot(d['d_calls'][dl], d['d_dealer'][dl].astype(np.int64), seat)
    rows = (model.index([str(s) for s in d['systems']]) if table is None else table)[d['d_sys'][dl]]
    return xh, xa, d['label'][ix].astype(np.float32), rows[np.arange(len(ix)), seat % 2], rows[np.arange(len(ix)), 1 - seat % 2]


def view(rng, own, opp, weights):
    """Hide declarations: weights = P(declared), P(both hidden), P(each side hidden with 1/2)."""
    mode = np.searchsorted(np.cumsum(weights), rng.random(len(own)) * np.sum(weights), side='right')
    keep_own = (mode == 0) | ((mode == 2) & (rng.random(len(own)) >= .5))
    keep_opp = (mode == 0) | ((mode == 2) & (rng.random(len(own)) >= .5))
    return np.where(keep_own, own, 0), np.where(keep_opp, opp, 0)


def parts_of(xa, gate, own, opp):
    """For each basis table in use: (k, rows using it or None for all, their effective input)."""
    g_own, g_opp = gate[own], gate[opp]
    xa_own = xa * OWN_COLS
    xa_opp = xa - xa_own
    parts = []
    for k in range(gate.shape[1]):
        a, b = g_own[:, k], g_opp[:, k]
        used = (a != 0) | (b != 0)
        if not used.any():
            continue
        if (a == 1).all() and (b == 1).all():
            parts.append((k, None, xa))
        else:
            rows = np.flatnonzero(used)
            parts.append((k, rows, a[rows, None] * xa_own[rows] + b[rows, None] * xa_opp[rows]))
    return parts


def forward(p, xh, parts):
    a = xh @ p['Wh'] + p['b0']
    for k, rows, x in parts:
        if rows is None:
            a += x @ p['Wa'][k]
        else:
            a[rows] += x @ p['Wa'][k]
    z0 = np.maximum(a, 0)
    z1 = np.maximum(z0 @ p['W1'] + p['b1'], 0)
    z2 = np.maximum(z1 @ p['W2'] + p['b2'], 0)
    return (z2 @ p['Wo'] + p['bo'])[:, 0], (z0, z1, z2)


def gradients(p, xh, parts, y, out, acts):
    """Gradient of the mean binary cross-entropy. Keys: layer names, and ('Wa', k) per table used."""
    z0, z1, z2 = acts
    d = ((np.exp(-np.logaddexp(0.0, -out)) - y) / len(y))[:, None].astype(xh.dtype)
    g = {'Wo': z2.T @ d, 'bo': d.sum(0)}
    d = (d @ p['Wo'].T) * (z2 > 0)
    g['W2'], g['b2'] = z1.T @ d, d.sum(0)
    d = (d @ p['W2'].T) * (z1 > 0)
    g['W1'], g['b1'] = z0.T @ d, d.sum(0)
    d = (d @ p['W1'].T) * (z0 > 0)
    g['Wh'], g['b0'] = xh.T @ d, d.sum(0)
    for k, rows, x in parts:
        g['Wa', k] = x.T @ (d if rows is None else d[rows])
    return g


def bce(out, y):
    return float(np.mean(np.logaddexp(0.0, out) - y * out))


def evaluate(model, d, mode='declared', n=None, chunk=8000):
    """Validation loss and accuracy by example kind under one reading of the declarations.

    mode: 'declared'; 'unknown' (both sides hidden); 'wrong' (every declared system replaced
    by another system of the model, which must cost if the declaration is being used)."""
    N = len(d['label'])
    ix = np.arange(N) if n is None or n >= N else np.linspace(0, N - 1, n).astype(np.int64)      # evenly spaced, so every table is in it
    S = len(model.sys_ids)
    outs, ys = [], []
    for s in range(0, len(ix), chunk):
        xh, xa, y, own, opp = batch(model, d, ix[s:s + chunk])
        if mode == 'unknown':
            own, opp = np.zeros_like(own), np.zeros_like(opp)
        elif mode == 'wrong':
            if S < 3:
                raise ValueError('a wrong declaration needs at least two systems in the model')
            own, opp = (np.where(row > 0, row % (S - 1) + 1, 0) for row in (own, opp))
        elif mode != 'declared':
            raise ValueError(mode)
        outs.append(forward(model.p, xh, parts_of(xa, model.gate, own, opp))[0]); ys.append(y)
    out, y, kind = np.concatenate(outs), np.concatenate(ys), d['kind'][ix]
    right = (out > 0) == (y > 0.5)
    return dict(loss=bce(out, y), true=float(right[kind == 0].mean()), random=float(right[kind == 1].mean()), near=float(right[kind == 2].mean()), examples=len(ix))


def by_table(model, d, modes=('declared', 'unknown', 'wrong')):
    """evaluate() separately for each (North-South, East-West) pairing in the data."""
    systems = [str(s) for s in d['systems']]
    rows = []
    for ns, ew in sorted({tuple(t) for t in d['d_sys'].tolist()}):
        ix = np.flatnonzero((d['d_sys'][d['deal']] == (ns, ew)).all(axis=1))
        sub = dict(d, **{k: d[k][ix] for k in ('deal', 'seat', 'length', 'hon', 'label', 'kind')})
        known = [m for m in modes if m != 'wrong' or len(model.sys_ids) >= 3]
        rows.append(dict(ns=systems[ns], ew=systems[ew], **{m: evaluate(model, sub, m) for m in known}))
    return rows


def train(model, d, val=None, minutes=None, steps=None, views=(0.5, 0.25, 0.25), only=None, seed=0,
          batch_size=1024, lr=(2e-3, 1e-4), keep_best=True, checks=30, log=print):
    """Adam on the three views. Stop after `minutes` or `steps`.

    only: system ids. Their own correction tables are trained and every other array is frozen
    (adding a system without disturbing the others).
    With validation data the declared-view loss is checked `checks` times and at the end, and with
    keep_best the model ends as its best checked state, the starting state included, so a
    run on too little data cannot leave a system worse than it found it.
    Returns dict(steps, best_step, best_loss)."""
    if (minutes is None) == (steps is None):
        raise ValueError('give minutes or steps')
    p, gate = model.p, model.gate
    table = model.index([str(s) for s in d['systems']])
    if only is not None:
        missing = [s for s in only if s not in model.sys_ids[1:]]
        if missing:
            raise ValueError(f'not in the model: {missing}')
        trainable = {('Wa', model.sys_ids.index(s)) for s in only}
    else:
        trainable = set(LAYERS) | {('Wa', k) for k in range(len(model.sys_ids))}
    m, v, count = {}, {}, {}
    rng = np.random.default_rng(seed)
    N, step, t0, next_check, checked, done, rate = len(d['label']), 0, time.time(), 0.0, -1, False, 0.0
    best = dict(loss=np.inf, step=0, p=None)

    def check():
        r = evaluate(model, val, n=40000)
        if r['loss'] < best['loss']:
            best.update(loss=r['loss'], step=step, p={k: a.copy() for k, a in p.items()} if keep_best else None)
        if log:
            log(f'{(time.time() - t0) / 60:5.1f} min step {step} ({step * batch_size / N:.2f} passes) lr {rate:.5f}: declared val loss {r["loss"]:.4f}; '
                f'accuracy true {r["true"]:.3f}, random {r["random"]:.3f}, near {r["near"]:.3f}')

    while not done:
        order = rng.permutation(N)
        for s in range(0, max(N - batch_size, 0) + 1, batch_size):
            progress = (time.time() - t0) / (minutes * 60) if steps is None else step / steps
            if val is not None and progress >= min(next_check, 1) and checked != step:
                check()
                checked, next_check = step, progress + 1 / checks
            if progress >= 1:
                done = True
                break
            rate = (lr[1] + 0.5 * (lr[0] - lr[1]) * (1 + np.cos(np.pi * progress))) * min(1.0, (step + 1) / 200)
            xh, xa, y, own, opp = batch(model, d, np.sort(order[s:s + batch_size]), table)
            own, opp = view(rng, own, opp, views)
            parts = parts_of(xa, gate, own, opp)
            out, acts = forward(p, xh, parts)
            step += 1
            for key, g in gradients(p, xh, parts, y, out, acts).items():
                if key not in trainable:
                    continue
                if key not in m:
                    m[key], v[key], count[key] = np.zeros_like(g), np.zeros_like(g), 0
                count[key] += 1
                m[key] = 0.9 * m[key] + 0.1 * g
                v[key] = 0.999 * v[key] + 0.001 * g * g
                delta = (rate * (m[key] / (1 - 0.9 ** count[key])) / (np.sqrt(v[key] / (1 - 0.999 ** count[key])) + 1e-8)).astype(np.float32)
                if isinstance(key, tuple):
                    p['Wa'][key[1]] -= delta
                else:
                    p[key] = (p[key] - delta.reshape(p[key].shape)).astype(np.float32)
    if val is not None and keep_best and best['p'] is not None and best['step'] != step:
        model.p = best['p']
    return dict(steps=step, best_step=best['step'] if val is not None else step, best_loss=float(best['loss']) if val is not None else None)

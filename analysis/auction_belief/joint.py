import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
FEED = _os.environ.get('SDB_FEED', '/home/claude/wt/feed/recovery')        # folder holding artifacts/, episodes/ and runtime/ (the arena feed's recovery folder)
RUNTIME = _os.environ.get('SDB_RUNTIME', FEED + '/runtime')
"""Joint auction belief model for the opening leader (prototype).

Generates the declarer's and dummy's hands as tokens: shape (one of 560), then the
honours held in each suit (a subset of A K Q J T). Partner gets what remains and
spot cards are dealt uniformly, which is exact for the current bidder because it
sees a hand only as honours plus a count of low cards per suit. Every token is a
masked softmax, so the model has an exact likelihood and never emits an illegal layout.
"""
import math
import sys

import numpy as np
import autograd.numpy as anp
from autograd.scipy.special import logsumexp

sys.path.insert(0, HERE)
from gen import COMP, COMP_ID, MASKH, POP, MAX_SLOTS  # noqa: E402

H = 256
D_IN = 83 + 256
D_G = 56 + 20 + 4 + 76 + 1 + 14 + 5
LOG_N_TOTAL = math.lgamma(40) - 3 * math.lgamma(14)
EYE14 = np.eye(14, dtype=np.float32)
BITS5 = np.array([[(i >> j) & 1 for j in range(5)] for i in range(32)], np.float32)
LGAMMA = np.array([math.lgamma(i + 1) for i in range(14)])


def init(seed=0, hg=128):
    rng = np.random.default_rng(seed)
    w = lambda i, o, s=1.0: (rng.standard_normal((i, o)) * np.sqrt(2.0 / i) * s).astype(np.float32)
    z = lambda n: np.zeros(n, np.float32)
    p = dict(Ea=(rng.standard_normal((MAX_SLOTS * 38, H)) * 0.05).astype(np.float32),
             Wh=w(D_IN, H), b0=z(2 * H), W1=w(2 * H, 512), b1=z(512), W2=w(512, H), b2=z(H),
             Ws1=w(H, 256), bs1=z(256), Wo1=w(256, 560, 0.1), bo1=z(560),
             Ws2=w(H + 76, 256), bs2=z(256), Wo2=w(256, 560, 0.1), bo2=z(560),
             Wc=w(H, hg), Wg=w(hg + D_G, 256), bg=z(256), Wgo=w(256, 32, 0.1), bgo=z(32))
    return p


def onehot_len(length):
    return EYE14[length].reshape(len(length), 56)


def hon_bits(hon):
    return BITS5[hon].reshape(len(hon), 20)


def hand_type(length, hon):
    return np.concatenate([onehot_len(length), hon_bits(hon)], axis=1)


def honour_inputs(own_len, own_hon, other_type, flag, avail, low):
    """Inputs, masks and targets for the four honour tokens of one hand. Returns (4B, D_G), (4B,32), (4B,)."""
    B = len(own_len)
    xs, ms, ts = [], [], []
    shape = onehot_len(own_len)
    for s in range(4):
        prefix = np.zeros((B, 4), np.int64)
        prefix[:, :s] = own_hon[:, :s]
        suit = np.zeros((B, 4), np.float32); suit[:, s] = 1
        xs.append(np.concatenate([shape, hon_bits(prefix), suit, other_type, np.full((B, 1), flag, np.float32),
                                  EYE14[own_len[:, s]], BITS5[avail[:, s]]], axis=1))
        ms.append(MASKH[avail[:, s], own_len[:, s], np.clip(low[:, s], 0, 8)])
        ts.append(own_hon[:, s])
    return np.concatenate(xs), np.concatenate(ms).astype(np.float32), np.concatenate(ts)


def prepare(d, ix):
    """Batch tensors from stored rows (plain NumPy, no gradients)."""
    g = lambda k: d[k][ix].astype(np.int64)
    n, avail, low = g('n'), g('avail'), g('low')
    D_len, D_hon, M_len, M_hon = g('D_len'), g('D_hon'), g('M_len'), g('M_hon')
    D_low = D_len - POP[D_hon]
    B = len(n)
    x = np.concatenate([d['xh'][ix].astype(np.float32), d['state'][ix].astype(np.float32)], axis=1)
    typeD = hand_type(D_len, D_hon)
    m1 = (COMP[None, :, :] <= n[:, None, :]).all(-1).astype(np.float32)
    m2 = (COMP[None, :, :] <= (n - D_len)[:, None, :]).all(-1).astype(np.float32)
    t1 = COMP_ID[D_len[:, 0], D_len[:, 1], D_len[:, 2]]
    t2 = COMP_ID[M_len[:, 0], M_len[:, 1], M_len[:, 2]]
    gD = honour_inputs(D_len, D_hon, np.zeros((B, 76), np.float32), 0., avail, low)
    gM = honour_inputs(M_len, M_hon, typeD, 1., avail & ~D_hon, low - D_low)
    P_low = low - D_low - (M_len - POP[M_hon])
    log_n = (LGAMMA[low] - LGAMMA[D_low] - LGAMMA[M_len - POP[M_hon]] - LGAMMA[P_low]).sum(1)
    return dict(x=x, slots=slot_onehot(d['slots'][ix]), typeD=typeD, m1=m1, m2=m2, t1=t1, t2=t2,
                gx=np.concatenate([gD[0], gM[0]]), gm=np.concatenate([gD[1], gM[1]]),
                gt=np.concatenate([gD[2], gM[2]]), log_n=log_n)


def slot_onehot(slots):
    """(B, slots) indices -> dense (B, slots*38) one-hot; the empty-slot index is dropped."""
    slots = np.asarray(slots).astype(np.int64)
    oh = np.zeros((len(slots), MAX_SLOTS * 38 + 1), np.float32)
    np.put_along_axis(oh, slots, 1.0, axis=1)
    return oh[:, :-1]


def relu(x):
    return anp.maximum(x, 0)


def context(p, x, slots):
    a = anp.dot(slots, p['Ea'])
    z = relu(anp.concatenate([a, anp.dot(x, p['Wh'])], axis=1) + p['b0'])
    z = relu(anp.dot(z, p['W1']) + p['b1'])
    return relu(anp.dot(z, p['W2']) + p['b2'])


def masked_logp(logits, mask):
    z = logits + (mask - 1.0) * 1e9
    return z - logsumexp(z, axis=1, keepdims=True)


def shape1(p, ctx):
    return anp.dot(relu(anp.dot(ctx, p['Ws1']) + p['bs1']), p['Wo1']) + p['bo1']


def shape2(p, ctx, typeD):
    return anp.dot(relu(anp.dot(anp.concatenate([ctx, typeD], axis=1), p['Ws2']) + p['bs2']), p['Wo2']) + p['bo2']


def honours(p, cg, gx):
    return anp.dot(relu(anp.dot(anp.concatenate([cg, gx], axis=1), p['Wg']) + p['bg']), p['Wgo']) + p['bgo']


def token_logps(p, b):
    """Per-row log-probabilities: shape D, shape M, and the eight honour tokens summed."""
    B = len(b['x'])
    ctx = context(p, b['x'], b['slots'])
    l1 = masked_logp(shape1(p, ctx), b['m1'])[anp.arange(B), b['t1']]
    l2 = masked_logp(shape2(p, ctx, b['typeD']), b['m2'])[anp.arange(B), b['t2']]
    cg = anp.dot(ctx, p['Wc'])
    lg = masked_logp(honours(p, anp.concatenate([cg] * 8, axis=0), b['gx']), b['gm'])[anp.arange(8 * B), b['gt']]
    return l1, l2, anp.sum(anp.reshape(lg, (8, B)), axis=0)


def loss(p, b):
    l1, l2, lg = token_logps(p, b)
    return -anp.mean(l1 + l2 + lg)


def nats(p, b):
    """Log-likelihood of the true layout minus the uniform log-likelihood, per row."""
    l1, l2, lg = token_logps(p, b)
    return (l1 + l2 + lg) - b['log_n'] + LOG_N_TOTAL, (l1, l2, lg)


def sample(p, row, n, rng):
    """Draw n hand-type configurations for one lead. row: dict of single-row arrays (as stored)."""
    g = lambda k: np.repeat(row[k].astype(np.int64)[None, :], n, axis=0)
    nn, avail, low = g('n'), g('avail'), g('low')
    x = np.concatenate([row['xh'].astype(np.float32), row['state'].astype(np.float32)])[None, :]
    ctx1 = context(p, x, slot_onehot(row['slots'][None, :]))
    ctx = np.repeat(ctx1, n, axis=0)
    cg = ctx @ p['Wc']

    logq = np.zeros(n)

    def draw(logits, mask):
        z = np.where(mask > 0, logits, -np.inf).astype(np.float64)
        z -= z.max(axis=1, keepdims=True)
        pr = np.exp(z); pr /= pr.sum(axis=1, keepdims=True)
        u = rng.random((len(pr), 1))
        k = np.minimum((pr.cumsum(axis=1) < u).sum(axis=1), pr.shape[1] - 1)
        bad = pr[np.arange(len(pr)), k] <= 0          # guard against a rounding step onto a masked option
        if bad.any():
            k[bad] = pr[bad].argmax(axis=1)
        logq[:] += np.log(pr[np.arange(len(pr)), k])
        return k

    def honour_tokens(own_len, other_type, flag, av, lo):
        hon = np.zeros((n, 4), np.int64)
        shape = onehot_len(own_len)
        for s in range(4):
            suit = np.zeros((n, 4), np.float32); suit[:, s] = 1
            gx = np.concatenate([shape, hon_bits(hon), suit, other_type, np.full((n, 1), flag, np.float32),
                                 EYE14[own_len[:, s]], BITS5[av[:, s]]], axis=1)
            mask = MASKH[av[:, s], own_len[:, s], np.clip(lo[:, s], 0, 8)]
            hon[:, s] = draw(honours(p, cg, gx), mask)
        return hon
    m1 = (COMP[None, :, :] <= nn[:, None, :]).all(-1)
    D_len = COMP[draw(shape1(p, ctx), m1)]
    D_hon = honour_tokens(D_len, np.zeros((n, 76), np.float32), 0., avail, low)
    D_low = D_len - POP[D_hon]
    typeD = hand_type(D_len, D_hon)
    m2 = (COMP[None, :, :] <= (nn - D_len)[:, None, :]).all(-1)
    M_len = COMP[draw(shape2(p, ctx, typeD), m2)]
    M_hon = honour_tokens(M_len, typeD, 1., avail & ~D_hon, low - D_low)
    M_low = M_len - POP[M_hon]
    log_n = (LGAMMA[low] - LGAMMA[D_low] - LGAMMA[M_low] - LGAMMA[low - D_low - M_low]).sum(1)
    return dict(D_len=D_len, D_hon=D_hon, M_len=M_len, M_hon=M_hon, logq=logq, log_n=log_n)


def deal_cards(leader_hand, types, rng):
    """Concrete hands (declarer, dummy, partner) for sampled types; spot cards uniform."""
    own = set(leader_hand)
    out = []
    for k in range(len(types['D_len'])):
        hands = [[], [], []]
        for s in range(4):
            dh, mh = int(types['D_hon'][k, s]), int(types['M_hon'][k, s])
            for j in range(5):
                c = 13 * s + 12 - j
                if c in own:
                    continue
                hands[0 if dh >> j & 1 else 1 if mh >> j & 1 else 2].append(c)
            lows = [13 * s + r for r in range(8) if 13 * s + r not in own]
            rng.shuffle(lows)
            dl = int(types['D_len'][k, s]) - POP[dh]
            ml = int(types['M_len'][k, s]) - POP[mh]
            hands[0] += lows[:dl]; hands[1] += lows[dl:dl + ml]; hands[2] += lows[dl + ml:]
        assert all(len(h) == 13 for h in hands), [len(h) for h in hands]
        out.append([sorted(h) for h in hands])
    return out
